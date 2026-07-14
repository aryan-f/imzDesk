import numpy as np
from scipy import ndimage
from skimage import morphology

import imzdesk.transforms as T
from imzdesk.core import Transform


def register(wsi, msi, target_mpp: float | tuple[float, float] | None = None, model: str = 'roman-bushuiev/DreaMS') -> Transform:
    """
    Register an MSI acquisition to a WSI.

    Parameters
    ----------
    wsi:
        Fixed whole-slide image.
    msi:
        Moving MSI acquisition.
    target_mpp:
        Registration raster resolution. Defaults to the axis-wise MSI mpp.
    model:
        Embedding model used for the MSI surrogate.

    Returns
    -------
    transform: Transform
        Transform mapping MSI surrogate pixel coordinates into WSI surrogate
        pixel coordinates.
    """
    if target_mpp is None:
        target_mpp = (msi.metadata.mpp.x, msi.metadata.mpp.y)
    fixed_mask = T.Compose([
        T.ToImage(target_mpp=target_mpp),
        T.OpticalDensity(),
        T.Threshold(),
    ])(wsi)
    moving_mask = T.Compose([
        T.ToRImage(),
        T.Normalize('tic'),
        T.Embed(model=model),
        T.Project(),
        T.ToImage(),
        T.Threshold(),
    ])(msi)

    transform = centroid_initialization(fixed_mask, moving_mask)
    transform = rotation_sweep(fixed_mask, moving_mask, transform)
    transform = chamfer_refine(fixed_mask, moving_mask, transform)
    transform = apply_wsi_crop_offset(wsi, target_mpp, transform)
    return transform


def apply_wsi_crop_offset(wsi, target_mpp: float | tuple[float, float], transform: Transform) -> Transform:
    """
    Convert a crop-local WSI transform into full-slide WSI coordinates.
    """
    if wsi.metadata.crop is None:
        return transform
    target_mpp = np.asarray(target_mpp if isinstance(target_mpp, tuple) else (target_mpp, target_mpp), dtype=np.float64)
    native_mpp = np.array([wsi.metadata.mpp.x, wsi.metadata.mpp.y], dtype=np.float64)
    slide_width, slide_height = wsi.slide.dimensions
    crop_box = wsi.metadata.crop
    offset = np.array([crop_box.x * slide_width, crop_box.y * slide_height], dtype=np.float64) * native_mpp / target_mpp
    return Transform.translation(offset[0], offset[1]) @ transform


def centroid(mask, weights=None):
    """
    Return an ``(x, y)`` centroid for a mask or scalar image.
    """
    values = np.asarray(mask, dtype=np.float64)
    if weights is not None:
        values = values * np.asarray(weights, dtype=np.float64)
    total = values.sum()
    if total == 0:
        height, width = values.shape
        return np.array([(width - 1) / 2, (height - 1) / 2], dtype=np.float64)
    y, x = np.indices(values.shape)
    return np.array([(x * values).sum() / total, (y * values).sum() / total], dtype=np.float64)


def centroid_initialization(fixed_mask, moving_mask) -> Transform:
    """
    Initialize translation by aligning moving and fixed centroids.
    """
    fixed_centroid = centroid(fixed_mask)
    moving_centroid = centroid(moving_mask)
    shift = fixed_centroid - moving_centroid
    return Transform.translation(shift[0], shift[1])


def rotation_sweep(fixed_mask, moving_mask, transform: Transform, angle_step: float = 5.0, alpha: float = 0.25) -> Transform:
    """
    Sweep rotations and keep the transform with the best NCC/IoU score.
    """
    fixed = np.asarray(fixed_mask, dtype=bool)
    moving = np.asarray(moving_mask, dtype=bool)
    center = centroid(moving)
    best_transform = transform
    best_score = -np.inf
    for angle in np.deg2rad(np.arange(0, 360, angle_step)):
        candidate = transform @ Transform.rotation(angle, center=center)
        warped = warp(moving.astype(np.float32), candidate, fixed.shape, order=0) > 0.5
        score = (1 - alpha) * ncc(fixed, warped) + alpha * iou(fixed, warped)
        if score > best_score:
            best_score = score
            best_transform = candidate
    return best_transform


def chamfer_refine(fixed_mask, moving_mask, transform: Transform, max_iterations: int = 80, distance_clip: float = 25.0) -> Transform:
    """
    Refine a rigid transform with coordinate pattern search over Chamfer loss.
    """
    angle_step = np.deg2rad(2.0)
    translation_step = 5.0
    minimum_angle_step = np.deg2rad(0.1)
    minimum_translation_step = 0.25
    current = transform
    current_loss = chamfer_loss(fixed_mask, moving_mask, current, distance_clip=distance_clip)
    for _ in range(max_iterations):
        moves = [
            Transform.translation(translation_step, 0),
            Transform.translation(-translation_step, 0),
            Transform.translation(0, translation_step),
            Transform.translation(0, -translation_step),
            Transform.rotation(angle_step, center=centroid(moving_mask)),
            Transform.rotation(-angle_step, center=centroid(moving_mask)),
        ]
        improved = False
        for move in moves:
            candidate = current @ move
            loss = chamfer_loss(fixed_mask, moving_mask, candidate, distance_clip=distance_clip)
            if loss < current_loss:
                current = candidate
                current_loss = loss
                improved = True
                break
        if not improved:
            angle_step /= 2
            translation_step /= 2
            if angle_step < minimum_angle_step and translation_step < minimum_translation_step:
                break
    return current


def chamfer_loss(fixed_mask, moving_mask, transform: Transform, distance_clip: float = 25.0) -> float:
    """
    Symmetric clipped boundary Chamfer loss.
    """
    fixed = np.asarray(fixed_mask, dtype=bool)
    moving = np.asarray(moving_mask, dtype=bool)
    fixed_contour = contour(fixed)
    moving_contour = contour(moving)
    if not fixed_contour.any() or not moving_contour.any():
        return np.inf
    fixed_distance = ndimage.distance_transform_edt(~fixed_contour)
    moving_distance = ndimage.distance_transform_edt(~moving_contour)
    warped_moving_contour = warp(moving_contour.astype(np.float32), transform, fixed.shape, order=0) > 0.5
    warped_fixed_contour = warp(fixed_contour.astype(np.float32), transform.inverse(), moving.shape, order=0) > 0.5
    fixed_term = np.clip(fixed_distance[warped_moving_contour], 0, distance_clip).mean() if warped_moving_contour.any() else distance_clip
    moving_term = np.clip(moving_distance[warped_fixed_contour], 0, distance_clip).mean() if warped_fixed_contour.any() else distance_clip
    return (fixed_term + moving_term) / (2 * distance_clip)


def contour(mask):
    """
    Return a one-pixel binary contour for a mask.
    """
    mask = np.asarray(mask, dtype=bool)
    return mask ^ morphology.erosion(mask)


def warp(image, transform: Transform, output_shape, order: int = 1):
    """
    Warp ``image`` into ``output_shape`` using a moving-to-fixed transform.
    """
    inverse = transform.inverse()
    y, x = np.indices(output_shape)
    fixed_points = np.column_stack([x.ravel(), y.ravel()])
    moving_points = inverse.apply(fixed_points)
    sampled = ndimage.map_coordinates(
        np.asarray(image),
        [moving_points[:, 1], moving_points[:, 0]],
        order=order,
        mode='constant',
        cval=0,
    )
    return sampled.reshape(output_shape)


def iou(fixed_mask, moving_mask) -> float:
    """
    Intersection-over-union for two masks.
    """
    fixed = np.asarray(fixed_mask, dtype=bool)
    moving = np.asarray(moving_mask, dtype=bool)
    union = np.logical_or(fixed, moving).sum()
    if union == 0:
        return 0.0
    return np.logical_and(fixed, moving).sum() / union


def ncc(fixed_mask, moving_mask) -> float:
    """
    Normalized cross-correlation for two images or masks.
    """
    fixed = np.asarray(fixed_mask, dtype=np.float64)
    moving = np.asarray(moving_mask, dtype=np.float64)
    fixed = fixed - fixed.mean()
    moving = moving - moving.mean()
    denominator = np.sqrt((fixed ** 2).sum() * (moving ** 2).sum())
    if denominator == 0:
        return 0.0
    return (fixed * moving).sum() / denominator
