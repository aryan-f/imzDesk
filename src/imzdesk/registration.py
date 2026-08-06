import numpy as np
from scipy import ndimage
from skimage import morphology

import imzdesk.transforms as T
from imzdesk.core import Transform


def register(
    wsi,
    msi,
    target_mpp=None,
    model='roman-bushuiev/DreaMS',
    batch_size=128,
):
    """
    Register an MSI acquisition to a WSI.

    Parameters
    ----------
    wsi : imzdesk.io.WSI
        Fixed whole-slide image.
    msi : imzdesk.io.MSI
        Moving MSI acquisition.
    target_mpp : float or tuple of float, optional
        Registration raster resolution. Defaults to the axis-wise MSI mpp.
    model : str, default='roman-bushuiev/DreaMS'
        Embedding model used for the MSI surrogate.
    batch_size : int, default=128
        Number of spectra embedded in each inference batch.

    Returns
    -------
    Transform
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
        T.Embed(model=model, batch_size=batch_size),
        T.Project(),
        T.ToImage(),
        T.Threshold(),
    ])(msi)

    transform = centroid_initialization(fixed_mask, moving_mask)
    transform = rotation_sweep(fixed_mask, moving_mask, transform)
    transform = chamfer_refine(fixed_mask, moving_mask, transform)
    transform = apply_wsi_crop_offset(wsi, target_mpp, transform)
    return transform


def apply_wsi_crop_offset(wsi, target_mpp, transform):
    """
    Convert a crop-local WSI transform into full-slide WSI coordinates.

    Parameters
    ----------
    wsi : imzdesk.io.WSI
        Whole-slide image that supplied the fixed registration raster.
    target_mpp : float or tuple of float
        Registration raster resolution in microns per pixel.
    transform : Transform
        Transform expressed in crop-local WSI coordinates.

    Returns
    -------
    Transform
        Transform expressed in full-slide WSI coordinates.
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

    Parameters
    ----------
    mask : array-like
        Mask or scalar image.
    weights : array-like, optional
        Additional per-pixel weights.

    Returns
    -------
    numpy.ndarray
        Two-element ``(x, y)`` centroid.
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


def centroid_initialization(fixed_mask, moving_mask):
    """
    Initialize translation by aligning moving and fixed centroids.

    Parameters
    ----------
    fixed_mask : array-like
        Fixed binary mask.
    moving_mask : array-like
        Moving binary mask.

    Returns
    -------
    Transform
        Centroid-aligning translation.
    """
    fixed_centroid = centroid(fixed_mask)
    moving_centroid = centroid(moving_mask)
    shift = fixed_centroid - moving_centroid
    return Transform.translation(shift[0], shift[1])


def rotation_sweep(fixed_mask, moving_mask, transform, angle_step=5.0, alpha=0.25):
    """
    Keep the rotation with the best combined NCC and IoU score.

    Parameters
    ----------
    fixed_mask : array-like
        Fixed binary mask.
    moving_mask : array-like
        Moving binary mask.
    transform : Transform
        Initial moving-to-fixed transform.
    angle_step : float, default=5.0
        Rotation increment in degrees.
    alpha : float, default=0.25
        IoU contribution to the combined score.

    Returns
    -------
    Transform
        Best transform found by the sweep.
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


def chamfer_refine(fixed_mask, moving_mask, transform, max_iterations=80, distance_clip=25.0):
    """
    Refine a rigid transform by pattern search over Chamfer loss.

    Parameters
    ----------
    fixed_mask : array-like
        Fixed binary mask.
    moving_mask : array-like
        Moving binary mask.
    transform : Transform
        Initial moving-to-fixed transform.
    max_iterations : int, default=80
        Maximum number of pattern-search iterations.
    distance_clip : float, default=25.0
        Maximum contour distance included in the loss.

    Returns
    -------
    Transform
        Refined transform.
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


def chamfer_loss(fixed_mask, moving_mask, transform, distance_clip=25.0):
    """
    Calculate symmetric clipped boundary Chamfer loss.

    Parameters
    ----------
    fixed_mask : array-like
        Fixed binary mask.
    moving_mask : array-like
        Moving binary mask.
    transform : Transform
        Moving-to-fixed transform.
    distance_clip : float, default=25.0
        Maximum contour distance included in the loss.

    Returns
    -------
    float
        Normalized symmetric Chamfer loss.
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

    Parameters
    ----------
    mask : array-like
        Binary mask.

    Returns
    -------
    numpy.ndarray
        Binary contour mask.
    """
    mask = np.asarray(mask, dtype=bool)
    return mask ^ morphology.erosion(mask)


def warp(image, transform, output_shape, order=1):
    """
    Warp an image using a moving-to-fixed transform.

    Parameters
    ----------
    image : array-like
        Moving image.
    transform : Transform
        Moving-to-fixed transform.
    output_shape : tuple of int
        Fixed output ``(height, width)``.
    order : int, default=1
        Spline interpolation order.

    Returns
    -------
    numpy.ndarray
        Warped image.
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


def iou(fixed_mask, moving_mask):
    """
    Calculate intersection over union for two masks.

    Parameters
    ----------
    fixed_mask : array-like
        First binary mask.
    moving_mask : array-like
        Second binary mask.

    Returns
    -------
    float
        Intersection-over-union score.
    """
    fixed = np.asarray(fixed_mask, dtype=bool)
    moving = np.asarray(moving_mask, dtype=bool)
    union = np.logical_or(fixed, moving).sum()
    if union == 0:
        return 0.0
    return np.logical_and(fixed, moving).sum() / union


def ncc(fixed_mask, moving_mask):
    """
    Calculate normalized cross-correlation for two images or masks.

    Parameters
    ----------
    fixed_mask : array-like
        First image or mask.
    moving_mask : array-like
        Second image or mask.

    Returns
    -------
    float
        Normalized cross-correlation score.
    """
    fixed = np.asarray(fixed_mask, dtype=np.float64)
    moving = np.asarray(moving_mask, dtype=np.float64)
    fixed = fixed - fixed.mean()
    moving = moving - moving.mean()
    denominator = np.sqrt((fixed ** 2).sum() * (moving ** 2).sum())
    if denominator == 0:
        return 0.0
    return (fixed * moving).sum() / denominator
