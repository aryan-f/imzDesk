from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from scipy import ndimage

from imzdesk.core import DImage, Geometry, PairedImage, RImage, SImage, SpatialImage, Transform
from imzdesk.io import MSI, WSI
from imzdesk.transforms._random import WorkerRandomMixin
from imzdesk.transforms.base import Transform as ImageTransform
from imzdesk.transforms.spatial import RandomCrop, _mpp, _native_spatial


_INTERPOLATION_ORDERS = {
    'nearest': 0,
    'bilinear': 1,
    'bicubic': 3,
}


def _size(value: int | Sequence[int]) -> tuple[int, int]:
    size = (value, value) if isinstance(value, int) else tuple(value)
    if len(size) != 2 or any(dimension <= 0 for dimension in size):
        raise ValueError('Size must contain two positive dimensions.')
    return int(size[0]), int(size[1])


def _pair_spatials(image: PairedImage) -> tuple[SpatialImage, SpatialImage]:
    wsi = image.wsi if isinstance(image.wsi, SpatialImage) else _native_spatial(image.wsi)
    if isinstance(image.msi, SpatialImage):
        msi = image.msi
    else:
        x_mpp, y_mpp = _mpp(image.msi)
        frame = Transform.scale((x_mpp, y_mpp))
        if image.registration is not None:
            frame = frame @ image.registration
        msi = _native_spatial(image.msi, frame)
    return wsi, msi


def _geometry(frame: Transform, width: int, height: int) -> Geometry:
    linear = frame.matrix[:2, :2]
    mpp = (np.linalg.norm(linear[:, 0]), np.linalg.norm(linear[:, 1]))
    origin = frame.apply([[0, 0]])[0]
    return Geometry(width=width, height=height, mpp=mpp, origin=origin)


def _fill_values(fill, channels: int):
    if np.isscalar(fill):
        return [fill] * channels
    values = list(fill)
    if len(values) != channels:
        raise ValueError(f'Fill must be a scalar or contain {channels} channel values.')
    return values


def _warp_array(image, source_from_output: Transform, shape, interpolation, fill, mode):
    order = _INTERPOLATION_ORDERS[interpolation]
    output_height, output_width = shape
    y, x = np.indices((output_height, output_width), dtype=np.float64)
    output = np.column_stack([x.ravel(), y.ravel()])
    source = source_from_output.apply(output)
    coordinates = [source[:, 1], source[:, 0]]
    if image.ndim == 2:
        return ndimage.map_coordinates(
            image,
            coordinates,
            order=order,
            mode=mode,
            cval=fill,
        ).reshape(shape)

    trailing_shape = image.shape[2:]
    flattened = image.reshape(*image.shape[:2], -1)
    fills = _fill_values(fill, flattened.shape[2])
    channels = [
        ndimage.map_coordinates(
            flattened[..., channel],
            coordinates,
            order=order,
            mode=mode,
            cval=fills[channel],
        ).reshape(shape)
        for channel in range(flattened.shape[2])
    ]
    return np.stack(channels, axis=-1).reshape(*shape, *trailing_shape)


def _subset_ragged(image: RImage, indices, coordinates) -> RImage:
    positions = []
    values = []
    offsets = [0]
    for index in indices:
        pixel_positions, pixel_values = image.pixel(index)
        positions.append(pixel_positions)
        values.append(pixel_values)
        offsets.append(offsets[-1] + len(pixel_positions))
    return RImage(
        coordinates=coordinates,
        positions=np.concatenate(positions) if positions else np.array([], dtype=image.positions.dtype),
        values=np.concatenate(values) if values else np.array([], dtype=image.values.dtype),
        offsets=np.asarray(offsets, dtype=np.int64),
    )


def _warp_points(image, output_from_source: Transform, shape):
    output_height, output_width = shape
    coordinates = np.rint(output_from_source.apply(image.coordinates)).astype(np.int64)
    keep = (
        (coordinates[:, 0] >= 0)
        & (coordinates[:, 0] < output_width)
        & (coordinates[:, 1] >= 0)
        & (coordinates[:, 1] < output_height)
    )
    indices = np.flatnonzero(keep)
    coordinates = coordinates[indices]
    if isinstance(image, RImage):
        return _subset_ragged(image, indices, coordinates)
    if isinstance(image, SImage):
        return SImage(values=image.values[indices], coordinates=coordinates)
    return DImage(values=image.values[indices], coordinates=coordinates)


def _reindex_spatial(
    image: SpatialImage,
    source_from_output: Transform,
    shape: tuple[int, int],
    interpolation: str = 'nearest',
    fill=0,
    mode: str = 'constant',
    frame_from_output: Transform | None = None,
    point_output_from_source: Transform | None = None,
) -> SpatialImage:
    if interpolation not in _INTERPOLATION_ORDERS:
        raise ValueError(f'Unknown interpolation: {interpolation}')
    data = image.data
    if isinstance(data, np.ndarray):
        output = _warp_array(data, source_from_output, shape, interpolation, fill, mode)
    elif isinstance(data, (RImage, SImage, DImage)):
        output = _warp_points(
            data,
            point_output_from_source or source_from_output.inverse(),
            shape,
        )
    elif isinstance(data, MSI):
        from imzdesk.transforms.msi import ToRImage
        output = _warp_points(
            ToRImage()(data),
            point_output_from_source or source_from_output.inverse(),
            shape,
        )
    elif isinstance(data, WSI):
        raise TypeError(
            'Full-frame geometric augmentation of a WSI requires an in-memory crop. '
            'Apply RandomCrop, CenterCrop, or ToImage first.'
        )
    else:
        raise TypeError(f'Geometric transforms do not support {type(data).__name__}.')

    height, width = shape
    frame = image.pixel_to_reference @ (frame_from_output or source_from_output)
    return SpatialImage(output, _geometry(frame, width, height), frame)


def _restore(original, result: SpatialImage):
    return result if isinstance(original, SpatialImage) else result.data


def _apply_local(image, operation):
    if isinstance(image, PairedImage):
        wsi, msi = _pair_spatials(image)
        wsi = operation(wsi)
        msi = operation(msi)
        registration = None
        if image.registration is not None:
            registration = wsi.pixel_to_reference.inverse() @ msi.pixel_to_reference
        return PairedImage(wsi, msi, registration)
    spatial = image if isinstance(image, SpatialImage) else _native_spatial(image)
    return _restore(image, operation(spatial))


class RandomHorizontalFlip(ImageTransform, WorkerRandomMixin):
    """Flip one image or both members of a pair horizontally."""

    def __init__(self, p: float = 0.5, seed: int | None = None):
        if not 0 <= p <= 1:
            raise ValueError('Probability must be between zero and one.')
        self.p = p
        self._init_random(seed)

    def __call__(self, image):
        if self._rng().random() >= self.p:
            return image

        def flip(spatial):
            width = spatial.geometry.width
            mapping = Transform([[-1, 0, width - 1], [0, 1, 0], [0, 0, 1]])
            return _reindex_spatial(spatial, mapping, (spatial.geometry.height, width))

        return _apply_local(image, flip)


class RandomVerticalFlip(ImageTransform, WorkerRandomMixin):
    """Flip one image or both members of a pair vertically."""

    def __init__(self, p: float = 0.5, seed: int | None = None):
        if not 0 <= p <= 1:
            raise ValueError('Probability must be between zero and one.')
        self.p = p
        self._init_random(seed)

    def __call__(self, image):
        if self._rng().random() >= self.p:
            return image

        def flip(spatial):
            height = spatial.geometry.height
            mapping = Transform([[1, 0, 0], [0, -1, height - 1], [0, 0, 1]])
            return _reindex_spatial(spatial, mapping, (height, spatial.geometry.width))

        return _apply_local(image, flip)


class RandomRotate90(ImageTransform, WorkerRandomMixin):
    """Rotate by a randomly selected multiple of 90 degrees."""

    def __init__(self, p: float = 0.5, choices=(1, 2, 3), seed: int | None = None):
        if not 0 <= p <= 1:
            raise ValueError('Probability must be between zero and one.')
        choices = tuple(int(choice) % 4 for choice in choices)
        if not choices:
            raise ValueError('At least one rotation choice is required.')
        self.p = p
        self.choices = choices
        self._init_random(seed)

    def __call__(self, image):
        if self._rng().random() >= self.p:
            return image
        turns = int(self._rng().choice(self.choices))

        def rotate(spatial):
            width, height = spatial.geometry.width, spatial.geometry.height
            if turns == 0:
                return spatial
            if turns == 1:
                mapping = Transform([[0, -1, width - 1], [1, 0, 0], [0, 0, 1]])
                shape = (width, height)
            elif turns == 2:
                mapping = Transform([[-1, 0, width - 1], [0, -1, height - 1], [0, 0, 1]])
                shape = (height, width)
            else:
                mapping = Transform([[0, 1, 0], [-1, 0, height - 1], [0, 0, 1]])
                shape = (width, height)
            return _reindex_spatial(spatial, mapping, shape)

        return _apply_local(image, rotate)


class CenterCrop(RandomCrop):
    """Crop the center of one image or the shared center of a registered pair."""

    def __init__(self, size, mpp=None):
        super().__init__(size=size, mpp=mpp)

    def _sample_polygon(self, polygon):
        polygon = self._unique_vertices(polygon)
        if len(polygon) == 1:
            return polygon[0].copy()
        following = np.roll(polygon, -1, axis=0)
        cross = polygon[:, 0] * following[:, 1] - polygon[:, 1] * following[:, 0]
        area = cross.sum() / 2
        if abs(area) <= 1e-12:
            return (polygon.min(axis=0) + polygon.max(axis=0)) / 2
        return (
            ((polygon + np.roll(polygon, -1, axis=0)) * cross[:, None]).sum(axis=0)
            / (6 * area)
        )


class Pad(ImageTransform):
    """Pad an in-memory image while retaining its spatial frame."""

    def __init__(self, padding: int | Sequence[int], fill=0):
        if isinstance(padding, int):
            padding = (padding,) * 4
        elif len(padding) == 2:
            padding = (padding[0], padding[1], padding[0], padding[1])
        elif len(padding) != 4:
            raise ValueError('Padding must be an int or contain two or four values.')
        if any(value < 0 for value in padding):
            raise ValueError('Padding values must be nonnegative.')
        self.padding = tuple(int(value) for value in padding)
        self.fill = fill

    def __call__(self, image):
        left, top, right, bottom = self.padding

        def pad(spatial):
            shape = (
                spatial.geometry.height + top + bottom,
                spatial.geometry.width + left + right,
            )
            mapping = Transform.translation(-left, -top)
            return _reindex_spatial(spatial, mapping, shape, fill=self.fill)

        return _apply_local(image, pad)


class Resize(ImageTransform):
    """Resize an image grid while preserving its physical field of view."""

    def __init__(self, size, interpolation: str = 'bilinear'):
        self.size = _size(size)
        if interpolation not in _INTERPOLATION_ORDERS:
            raise ValueError(f'Unknown interpolation: {interpolation}')
        self.interpolation = interpolation

    def _resize(self, spatial: SpatialImage, size=None):
        size = self.size if size is None else size
        output_height, output_width = size
        input_width, input_height = spatial.geometry.width, spatial.geometry.height
        factors = (input_width / output_width, input_height / output_height)
        frame_mapping = Transform.scale(factors)
        sampling_mapping = Transform.translation(
            (factors[0] - 1) / 2,
            (factors[1] - 1) / 2,
        ) @ frame_mapping
        if isinstance(spatial.data, WSI):
            target_mpp = tuple(spatial.geometry.mpp * np.array([
                factors[0],
                factors[1],
            ]))
            output = spatial.data.read_region((0, 0), size, target_mpp=target_mpp)
            frame = spatial.pixel_to_reference @ frame_mapping
            return SpatialImage(output, _geometry(frame, output_width, output_height), frame)
        return _reindex_spatial(
            spatial,
            sampling_mapping,
            size,
            self.interpolation,
            mode='nearest',
            frame_from_output=frame_mapping,
            point_output_from_source=frame_mapping.inverse(),
        )

    def __call__(self, image):
        return _apply_local(image, self._resize)


class Resample(Resize):
    """Resample at a target physical resolution while preserving field of view."""

    def __init__(self, mpp: float | Sequence[float], interpolation: str = 'bilinear'):
        mpp = (mpp, mpp) if isinstance(mpp, (int, float)) else tuple(mpp)
        if len(mpp) != 2 or any(value <= 0 for value in mpp):
            raise ValueError('Resolution must contain two positive values.')
        self.mpp = np.asarray(mpp, dtype=np.float64)
        self.interpolation = interpolation
        if interpolation not in _INTERPOLATION_ORDERS:
            raise ValueError(f'Unknown interpolation: {interpolation}')

    def __call__(self, image):
        def resample(spatial):
            width = max(1, round(spatial.geometry.width * spatial.geometry.mpp[0] / self.mpp[0]))
            height = max(1, round(spatial.geometry.height * spatial.geometry.mpp[1] / self.mpp[1]))
            return self._resize(spatial, (height, width))

        return _apply_local(image, resample)


class RandomResizedCrop(ImageTransform, WorkerRandomMixin):
    """Crop a random shared physical field and rasterize it to a fixed size."""

    def __init__(
        self,
        size,
        scale=(0.08, 1.0),
        ratio=(3 / 4, 4 / 3),
        seed: int | None = None,
    ):
        self.size = _size(size)
        if len(scale) != 2 or scale[0] <= 0 or scale[0] > scale[1] or scale[1] > 1:
            raise ValueError('Scale must be an increasing pair between zero and one.')
        if len(ratio) != 2 or ratio[0] <= 0 or ratio[0] > ratio[1]:
            raise ValueError('Ratio must contain an increasing pair of positive values.')
        self.scale = tuple(scale)
        self.ratio = tuple(ratio)
        self._init_random(seed)

    @staticmethod
    def _overlap(image):
        if isinstance(image, PairedImage):
            if image.registration is None:
                raise ValueError('A registered pair is required for a shared random crop.')
            images = _pair_spatials(image)
        else:
            images = (image if isinstance(image, SpatialImage) else _native_spatial(image),)
        bounds = [RandomCrop._bounds(item) for item in images]
        lower = np.max([item[0] for item in bounds], axis=0)
        upper = np.min([item[1] for item in bounds], axis=0)
        return np.maximum(upper - lower, 0)

    def __call__(self, image):
        overlap = self._overlap(image)
        area = overlap.prod()
        log_ratio = np.log(self.ratio)
        for _ in range(10):
            target_area = area * self._rng().uniform(*self.scale)
            aspect = np.exp(self._rng().uniform(*log_ratio))
            width = np.sqrt(target_area * aspect)
            height = np.sqrt(target_area / aspect)
            if width <= overlap[0] and height <= overlap[1]:
                mpp = (width / self.size[1], height / self.size[0])
                seed = int(self._rng().integers(0, np.iinfo(np.int64).max))
                try:
                    return RandomCrop(self.size, mpp=mpp, seed=seed)(image)
                except ValueError:
                    continue

        aspect = np.clip(overlap[0] / max(overlap[1], 1e-12), *self.ratio)
        width = min(overlap[0], overlap[1] * aspect)
        height = min(overlap[1], overlap[0] / aspect)
        mpp = (width / self.size[1], height / self.size[0])
        return CenterCrop(self.size, mpp=mpp)(image)


class RandomAffine(ImageTransform, WorkerRandomMixin):
    """Apply a random affine reparameterization to one image or a pair."""

    def __init__(
        self,
        degrees,
        translate=None,
        scale=None,
        shear=None,
        interpolation: str = 'nearest',
        fill=0,
        seed: int | None = None,
    ):
        self.degrees = self._range(degrees, symmetric=True, name='Degrees')
        if translate is not None and (len(translate) != 2 or any(value < 0 or value > 1 for value in translate)):
            raise ValueError('Translate must contain two fractions between zero and one.')
        self.translate = None if translate is None else tuple(translate)
        self.scale = None if scale is None else self._range(scale, name='Scale', positive=True)
        if shear is None:
            self.shear = (0.0, 0.0, 0.0, 0.0)
        elif isinstance(shear, (int, float)):
            value = abs(float(shear))
            self.shear = (-value, value, 0.0, 0.0)
        elif len(shear) == 2:
            self.shear = (*self._range(shear, name='Shear'), 0.0, 0.0)
        elif len(shear) == 4:
            self.shear = (*self._range(shear[:2], name='X shear'), *self._range(shear[2:], name='Y shear'))
        else:
            raise ValueError('Shear must be a number or contain two or four values.')
        if interpolation not in _INTERPOLATION_ORDERS:
            raise ValueError(f'Unknown interpolation: {interpolation}')
        self.interpolation = interpolation
        self.fill = fill
        self._init_random(seed)

    @staticmethod
    def _range(value, symmetric=False, name='Range', positive=False):
        if isinstance(value, (int, float)):
            values = (-float(value), float(value)) if symmetric else (float(value), float(value))
        else:
            if len(value) != 2:
                raise ValueError(f'{name} must be a number or contain two values.')
            values = tuple(float(item) for item in value)
        if values[0] > values[1] or (positive and values[0] <= 0):
            raise ValueError(f'{name} must be an increasing valid range.')
        return values

    def __call__(self, image):
        angle = np.deg2rad(self._rng().uniform(*self.degrees))
        scale = 1.0 if self.scale is None else self._rng().uniform(*self.scale)
        shear_x = np.deg2rad(self._rng().uniform(*self.shear[:2]))
        shear_y = np.deg2rad(self._rng().uniform(*self.shear[2:]))
        translation = (0.0, 0.0) if self.translate is None else (
            self._rng().uniform(-self.translate[0], self.translate[0]),
            self._rng().uniform(-self.translate[1], self.translate[1]),
        )

        def affine(spatial):
            width, height = spatial.geometry.width, spatial.geometry.height
            center = ((width - 1) / 2, (height - 1) / 2)
            cosine, sine = np.cos(angle), np.sin(angle)
            rotation = np.array([[cosine, -sine], [sine, cosine]])
            shear = np.array([[1, np.tan(shear_x)], [np.tan(shear_y), 1]])
            linear = rotation @ shear * scale
            forward = (
                Transform.translation(
                    center[0] + translation[0] * width,
                    center[1] + translation[1] * height,
                )
                @ Transform([[*linear[0], 0], [*linear[1], 0], [0, 0, 1]])
                @ Transform.translation(-center[0], -center[1])
            )
            return _reindex_spatial(
                spatial,
                forward.inverse(),
                (height, width),
                interpolation=self.interpolation,
                fill=self.fill,
            )

        return _apply_local(image, affine)
