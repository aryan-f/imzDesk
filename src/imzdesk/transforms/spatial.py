from __future__ import annotations

from collections.abc import Callable

import numpy as np
from scipy import ndimage, sparse

from imzdesk.core import (
    DImage,
    Geometry,
    PairedImage,
    RImage,
    RaggedTensor,
    SImage,
    SpatialImage,
    Transform,
)
from imzdesk.io import MSI, WSI
from imzdesk.transforms.base import Transform as ImageTransform


def _mpp(image: WSI | MSI) -> tuple[float, float]:
    metadata = image.metadata
    if metadata.mpp is None:
        raise ValueError(f'{type(image).__name__} metadata has no spatial resolution.')
    return metadata.mpp.x, metadata.mpp.y


def _shape(image) -> tuple[int, int]:
    if isinstance(image, MSI):
        coordinates = np.asarray(image.coordinates)
        if coordinates.ndim == 2 and len(coordinates) and coordinates.shape[1] >= 2:
            return int(np.ceil(coordinates[:, 1].max())) + 1, int(np.ceil(coordinates[:, 0].max())) + 1
        return image.metadata.height, image.metadata.width
    if isinstance(image, WSI):
        return image.metadata.height, image.metadata.width
    if isinstance(image, np.ndarray):
        if image.ndim < 2:
            raise ValueError('Spatial arrays must have at least two dimensions.')
        return image.shape[0], image.shape[1]
    if isinstance(image, (RImage, SImage, DImage)):
        coordinates = np.asarray(image.coordinates)
        if not len(coordinates):
            return 0, 0
        return int(np.ceil(coordinates[:, 1].max())) + 1, int(np.ceil(coordinates[:, 0].max())) + 1
    raise TypeError(f'Cannot determine spatial shape for {type(image).__name__}.')


def _native_spatial(image, pixel_to_reference: Transform | None = None) -> SpatialImage:
    x_mpp, y_mpp = _mpp(image) if isinstance(image, (WSI, MSI)) else (1.0, 1.0)
    height, width = _shape(image)
    geometry = Geometry(width=width, height=height, mpp=(x_mpp, y_mpp))
    return SpatialImage(
        data=image,
        geometry=geometry,
        pixel_to_reference=pixel_to_reference or Transform.scale((x_mpp, y_mpp)),
    )


def _replace_spatial_data(image: SpatialImage, data, source=None) -> SpatialImage:
    try:
        height, width = _shape(data)
    except (TypeError, ValueError):
        return SpatialImage(data, image.geometry, image.pixel_to_reference)
    if width == 0 or height == 0 or (width, height) == (image.geometry.width, image.geometry.height):
        return SpatialImage(data, image.geometry, image.pixel_to_reference)

    if isinstance(source, (RImage, SImage, DImage)):
        geometry = Geometry(
            width=width,
            height=height,
            mpp=tuple(image.geometry.mpp),
            origin=image.geometry.origin,
        )
        return SpatialImage(data, geometry, image.pixel_to_reference)

    factor = (image.geometry.width / width, image.geometry.height / height)
    geometry = Geometry(
        width=width,
        height=height,
        mpp=tuple(image.geometry.mpp * factor),
        origin=image.geometry.origin,
    )
    return SpatialImage(
        data=data,
        geometry=geometry,
        pixel_to_reference=image.pixel_to_reference @ Transform.scale(factor),
    )


def _apply_spatial(transform: Callable | None, image: SpatialImage) -> SpatialImage:
    if transform is None:
        return image
    transforms = getattr(transform, 'transforms', None)
    if transforms is not None:
        for operation in transforms:
            image = _apply_spatial(operation, image)
        return image
    from imzdesk.transforms.generic import ToImage

    source = image.data
    if (
        isinstance(transform, ToImage)
        and isinstance(source, WSI)
        and transform.crop
        and source.metadata.crop is not None
    ):
        raise ValueError(
            'Parallel cannot infer the spatial frame of ToImage(crop=True). '
            'Use crop=False or return a SpatialImage with an updated pixel_to_reference transform.'
        )
    if (
        isinstance(transform, ToImage)
        and isinstance(source, DImage)
        and transform.shape is None
    ):
        result = source.to_image(
            target_mpp=transform.target_mpp,
            shape=(image.geometry.height, image.geometry.width),
            crop=transform.crop,
        )
    else:
        result = transform(source)
    if isinstance(result, SpatialImage):
        return result
    return _replace_spatial_data(image, result, source=source)


class Parallel(ImageTransform):
    """Apply independent WSI and MSI pipelines while retaining spatial frames.

    Transforms returning raw image data must preserve the full spatial field,
    apart from a full-frame resize. A transform that crops, rotates, translates,
    or flips an image must return a ``SpatialImage`` describing its new frame.
    """

    def __init__(self, wsi: Callable | None = None, msi: Callable | None = None):
        self.wsi = wsi
        self.msi = msi

    def __call__(self, image: PairedImage) -> PairedImage:
        if not isinstance(image, PairedImage):
            raise TypeError('Parallel expects a PairedImage.')

        wsi = image.wsi if isinstance(image.wsi, SpatialImage) else _native_spatial(image.wsi)
        if isinstance(image.msi, SpatialImage):
            msi = image.msi
        else:
            msi_x_mpp, msi_y_mpp = _mpp(image.msi)
            pixel_to_reference = Transform.scale((msi_x_mpp, msi_y_mpp))
            if image.registration is not None:
                pixel_to_reference = pixel_to_reference @ image.registration
            msi = _native_spatial(image.msi, pixel_to_reference)

        wsi = _apply_spatial(self.wsi, wsi)
        msi = _apply_spatial(self.msi, msi)
        registration = None
        if image.registration is not None:
            registration = wsi.pixel_to_reference.inverse() @ msi.pixel_to_reference
        return PairedImage(wsi=wsi, msi=msi, registration=registration)


class RandomCrop(ImageTransform):
    """Randomly crop one image or a registered pair in a shared reference frame."""

    def __init__(
        self,
        size: int | tuple[int, int],
        mpp: float | tuple[float, float] | None = None,
        seed: int | None = None,
    ):
        self.size = (size, size) if isinstance(size, int) else size
        if len(self.size) != 2 or any(dimension <= 0 for dimension in self.size):
            raise ValueError('Crop size must contain two positive dimensions.')
        self.mpp = None if mpp is None else (mpp, mpp) if isinstance(mpp, (int, float)) else mpp
        if self.mpp is not None and (len(self.mpp) != 2 or any(value <= 0 for value in self.mpp)):
            raise ValueError('Crop resolution must contain two positive values.')
        self.seed = seed
        self._generator = None
        self._worker_id = None

    def __call__(self, image):
        if isinstance(image, PairedImage):
            return self._crop_pair(image)

        spatial = image if isinstance(image, SpatialImage) else _native_spatial(image)
        mpp = np.asarray(self.mpp or tuple(spatial.geometry.mpp), dtype=np.float64)
        origin = self._sample_origin((spatial,), mpp)
        result = self._crop_spatial(spatial, origin, mpp)
        return result if isinstance(image, SpatialImage) else result.data

    def _crop_pair(self, image: PairedImage) -> PairedImage:
        if image.registration is None:
            raise ValueError('A registered pair is required for a shared random crop.')

        wsi = image.wsi if isinstance(image.wsi, SpatialImage) else _native_spatial(image.wsi)
        if isinstance(image.msi, SpatialImage):
            msi = image.msi
        else:
            x_mpp, y_mpp = _mpp(image.msi)
            msi = _native_spatial(
                image.msi,
                Transform.scale((x_mpp, y_mpp)) @ image.registration,
            )

        mpp = np.asarray(self.mpp or tuple(wsi.geometry.mpp), dtype=np.float64)
        origin = self._sample_origin((wsi, msi), mpp)
        return PairedImage(
            wsi=self._crop_spatial(wsi, origin, mpp),
            msi=self._crop_spatial(msi, origin, mpp),
            registration=Transform.identity(),
        )

    def _sample_origin(self, images, mpp):
        crop_extent = np.array([self.size[1], self.size[0]], dtype=np.float64) * mpp
        bounds = [self._bounds(image) for image in images]
        lower = np.max([item[0] for item in bounds], axis=0)
        upper = np.min([item[1] for item in bounds], axis=0)
        maximum_origin = upper - crop_extent
        if np.any(maximum_origin < lower):
            self._raise_crop_error(crop_extent, lower, upper)

        polygon = np.array([
            lower,
            [maximum_origin[0], lower[1]],
            maximum_origin,
            [lower[0], maximum_origin[1]],
        ], dtype=np.float64)
        for image in images:
            polygon = self._clip_to_image(polygon, image, crop_extent)
            if not len(polygon):
                self._raise_crop_error(crop_extent, lower, upper)
        return self._sample_polygon(polygon)

    @staticmethod
    def _clip_to_image(polygon, image, crop_extent):
        inverse = image.pixel_to_reference.inverse().matrix
        if not np.allclose(inverse[2], [0, 0, 1]):
            raise ValueError('RandomCrop requires affine spatial transforms.')

        offsets = np.array([
            [0, 0],
            [crop_extent[0], 0],
            [crop_extent[0], crop_extent[1]],
            [0, crop_extent[1]],
        ], dtype=np.float64)
        limits = (image.geometry.width, image.geometry.height)
        for offset in offsets:
            for axis, limit in enumerate(limits):
                normal = inverse[axis, :2]
                constant = normal @ offset + inverse[axis, 2]
                polygon = RandomCrop._clip_half_plane(polygon, normal, limit - constant)
                polygon = RandomCrop._clip_half_plane(polygon, -normal, constant)
                if not len(polygon):
                    return polygon
        return polygon

    @staticmethod
    def _clip_half_plane(polygon, normal, limit):
        if not len(polygon):
            return polygon
        clipped = []
        previous = polygon[-1]
        previous_inside = normal @ previous <= limit + 1e-9
        for current in polygon:
            current_inside = normal @ current <= limit + 1e-9
            if current_inside != previous_inside:
                direction = current - previous
                denominator = normal @ direction
                if not np.isclose(denominator, 0):
                    fraction = (limit - normal @ previous) / denominator
                    clipped.append(previous + fraction * direction)
            if current_inside:
                clipped.append(current)
            previous = current
            previous_inside = current_inside
        return np.asarray(clipped, dtype=np.float64).reshape(-1, 2)

    def _sample_polygon(self, polygon):
        polygon = self._unique_vertices(polygon)
        if len(polygon) == 1:
            return polygon[0].copy()

        anchor = polygon[0]
        triangle_areas = np.array([
            abs(
                (polygon[index, 0] - anchor[0]) * (polygon[index + 1, 1] - anchor[1])
                - (polygon[index, 1] - anchor[1]) * (polygon[index + 1, 0] - anchor[0])
            ) / 2
            for index in range(1, len(polygon) - 1)
        ])
        total_area = triangle_areas.sum()
        if total_area <= 1e-12:
            distances = np.linalg.norm(polygon[:, None] - polygon[None, :], axis=2)
            start, stop = np.unravel_index(np.argmax(distances), distances.shape)
            fraction = self._rng().uniform()
            return fraction * polygon[start] + (1 - fraction) * polygon[stop]

        triangle = self._rng().choice(len(triangle_areas), p=triangle_areas / total_area) + 1
        root = np.sqrt(self._rng().uniform())
        fraction = self._rng().uniform()
        return (
            (1 - root) * anchor
            + root * (1 - fraction) * polygon[triangle]
            + root * fraction * polygon[triangle + 1]
        )

    @staticmethod
    def _unique_vertices(polygon):
        unique = []
        for vertex in polygon:
            if not any(np.allclose(vertex, existing, rtol=0, atol=1e-9) for existing in unique):
                unique.append(vertex)
        return np.asarray(unique, dtype=np.float64).reshape(-1, 2)

    @staticmethod
    def _raise_crop_error(crop_extent, lower, upper):
        overlap = np.maximum(upper - lower, 0)
        raise ValueError(
            'Crop does not fit within the available spatial overlap: '
            f'requested {tuple(crop_extent.tolist())} microns, '
            f'axis-aligned overlap {tuple(overlap.tolist())} microns.'
        )

    def _rng(self):
        try:
            from torch.utils.data import get_worker_info
            worker = get_worker_info()
        except ImportError:
            worker = None
        worker_id = None if worker is None else worker.id
        if self._generator is None or worker_id != self._worker_id:
            seed = self.seed
            if worker is not None:
                seed = worker.seed if seed is None else np.random.SeedSequence([seed, worker.id])
            self._generator = np.random.default_rng(seed)
            self._worker_id = worker_id
        return self._generator

    @staticmethod
    def _bounds(image: SpatialImage):
        width, height = image.geometry.width, image.geometry.height
        corners = np.array([[0, 0], [width, 0], [0, height], [width, height]], dtype=np.float64)
        transformed = image.pixel_to_reference.apply(corners)
        return transformed.min(axis=0), transformed.max(axis=0)

    def _crop_spatial(self, image: SpatialImage, origin, mpp) -> SpatialImage:
        data = image.data
        if isinstance(data, WSI) and np.allclose(image.pixel_to_reference.matrix[:2, :2], np.diag(_mpp(data))):
            source_origin = image.pixel_to_reference.inverse().apply([origin])[0]
            cropped = data.read_region(source_origin, self.size, tuple(mpp))
        elif isinstance(data, MSI):
            from imzdesk.transforms.msi import ToRImage
            cropped = self._crop_points(ToRImage()(data), image, origin, mpp)
        elif isinstance(data, np.ndarray):
            cropped = self._crop_array(data, image, origin, mpp)
        elif isinstance(data, (RImage, SImage, DImage)):
            cropped = self._crop_points(data, image, origin, mpp)
        else:
            raise TypeError(f'RandomCrop does not support {type(data).__name__}.')

        geometry = Geometry(
            width=self.size[1],
            height=self.size[0],
            mpp=tuple(mpp),
            origin=origin,
        )
        pixel_to_reference = Transform.translation(*origin) @ Transform.scale(tuple(mpp))
        return SpatialImage(cropped, geometry, pixel_to_reference)

    def _crop_array(self, image, spatial, origin, mpp):
        y, x = np.indices(self.size, dtype=np.float64)
        reference = np.column_stack([
            origin[0] + x.ravel() * mpp[0],
            origin[1] + y.ravel() * mpp[1],
        ])
        source = spatial.pixel_to_reference.inverse().apply(reference)
        coordinates = [source[:, 1], source[:, 0]]
        if image.ndim == 2:
            return ndimage.map_coordinates(image, coordinates, order=1, mode='constant').reshape(self.size)
        channels = [
            ndimage.map_coordinates(image[..., channel], coordinates, order=1, mode='constant').reshape(self.size)
            for channel in range(image.shape[2])
        ]
        return np.stack(channels, axis=-1)

    def _crop_points(self, image, spatial, origin, mpp):
        reference = spatial.pixel_to_reference.apply(image.coordinates)
        coordinates = (reference - origin) / mpp
        rounded = np.rint(coordinates).astype(np.int64)
        keep = (
            (rounded[:, 0] >= 0)
            & (rounded[:, 0] < self.size[1])
            & (rounded[:, 1] >= 0)
            & (rounded[:, 1] < self.size[0])
        )
        indices = np.flatnonzero(keep)
        cropped_coordinates = rounded[indices]
        if isinstance(image, RImage):
            positions = []
            values = []
            offsets = [0]
            for index in indices:
                pixel_positions, pixel_values = image.pixel(index)
                positions.append(pixel_positions)
                values.append(pixel_values)
                offsets.append(offsets[-1] + len(pixel_positions))
            return RImage(
                coordinates=cropped_coordinates,
                positions=np.concatenate(positions) if positions else np.array([], dtype=image.positions.dtype),
                values=np.concatenate(values) if values else np.array([], dtype=image.values.dtype),
                offsets=np.asarray(offsets, dtype=np.int64),
            )
        if isinstance(image, SImage):
            return SImage(values=image.values[indices], coordinates=cropped_coordinates)
        return DImage(values=image.values[indices], coordinates=cropped_coordinates)


class ToTensor(ImageTransform):
    """Convert supported image values and paired samples to PyTorch tensors."""

    def __init__(self, channel_first: bool = True, dtype=None):
        self.channel_first = channel_first
        self.dtype = dtype

    def __call__(self, image):
        try:
            import torch
        except ImportError as exception:
            raise ImportError('ToTensor requires the optional `torch` dependency.') from exception

        if isinstance(image, PairedImage):
            registration = None
            if image.registration is not None:
                registration = torch.as_tensor(image.registration.matrix, dtype=torch.float64)
            return PairedImage(
                wsi=self(image.wsi),
                msi=self(image.msi),
                registration=registration,
            )
        if isinstance(image, SpatialImage):
            if isinstance(image.data, DImage):
                return self(image.data.to_image(shape=(image.geometry.height, image.geometry.width)))
            if isinstance(image.data, SImage):
                dense = DImage(image.data.values.toarray(), image.data.coordinates)
                return self(dense.to_image(shape=(image.geometry.height, image.geometry.width)))
            return self(image.data)
        if isinstance(image, WSI):
            return self(image.to_image())
        if isinstance(image, MSI):
            from imzdesk.transforms.msi import ToRImage
            return self(ToRImage()(image))
        if isinstance(image, RImage):
            return RaggedTensor(
                coordinates=torch.as_tensor(image.coordinates),
                positions=torch.as_tensor(image.positions),
                values=torch.as_tensor(image.values),
                offsets=torch.as_tensor(image.offsets),
            )
        if isinstance(image, SImage):
            dense = DImage(image.values.toarray(), image.coordinates)
            return self(dense)
        if isinstance(image, DImage):
            return self(image.to_image())
        if isinstance(image, np.ndarray):
            values = image
            if self.channel_first and values.ndim == 3:
                values = np.moveaxis(values, -1, 0)
            elif self.channel_first and values.ndim == 2:
                values = values[None, ...]
            tensor = torch.as_tensor(np.ascontiguousarray(values))
            return tensor if self.dtype is None else tensor.to(self.dtype)
        if isinstance(image, sparse.spmatrix):
            return self(image.toarray())
        if isinstance(image, torch.Tensor):
            return image if self.dtype is None else image.to(self.dtype)
        raise TypeError(f'ToTensor does not support {type(image).__name__}.')
