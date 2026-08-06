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


def _size(value):
    """
    Normalize a scalar or pair into two positive dimensions.

    Parameters
    ----------
    value : int or sequence of int
        Scalar size or ``(height, width)`` pair.

    Returns
    -------
    tuple of int
        Two validated dimensions.
    """
    size = (value, value) if isinstance(value, int) else tuple(value)
    if len(size) != 2 or any(dimension <= 0 for dimension in size):
        raise ValueError('Size must contain two positive dimensions.')
    return int(size[0]), int(size[1])


def _pair_spatials(image):
    """
    Express both members of a registered pair as spatial images.

    Parameters
    ----------
    image : PairedImage
        Registered WSI-MSI pair.

    Returns
    -------
    tuple of SpatialImage
        WSI and MSI in their shared reference frame.
    """
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


def _geometry(frame, width, height):
    """
    Derive pixel-grid geometry from a reference-frame transform.

    Parameters
    ----------
    frame : Transform
        Pixel-to-reference transform.
    width : int
        Grid width.
    height : int
        Grid height.

    Returns
    -------
    Geometry
        Geometry represented by the transform and dimensions.
    """
    linear = frame.matrix[:2, :2]
    mpp = (np.linalg.norm(linear[:, 0]), np.linalg.norm(linear[:, 1]))
    origin = frame.apply([[0, 0]])[0]
    return Geometry(width=width, height=height, mpp=mpp, origin=origin)


def _fill_values(fill, channels):
    """
    Expand a scalar or validate channel-specific fill values.

    Parameters
    ----------
    fill : scalar or sequence
        Fill value specification.
    channels : int
        Number of flattened image channels.

    Returns
    -------
    list
        One fill value per channel.
    """
    if np.isscalar(fill):
        return [fill] * channels
    values = list(fill)
    if len(values) != channels:
        raise ValueError(f'Fill must be a scalar or contain {channels} channel values.')
    return values


def _warp_array(image, source_from_output, shape, interpolation, fill, mode):
    """
    Resample an array through an output-to-source transform.

    Parameters
    ----------
    image : numpy.ndarray
        Source image array.
    source_from_output : Transform
        Mapping from output pixels to source pixels.
    shape : tuple of int
        Output ``(height, width)``.
    interpolation : str
        Interpolation mode.
    fill : scalar or sequence
        Values used outside the source extent.
    mode : str
        SciPy boundary mode.

    Returns
    -------
    numpy.ndarray
        Resampled image array.
    """
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


def _subset_ragged(image, indices, coordinates):
    """
    Subset a ragged image and replace its spatial coordinates.

    Parameters
    ----------
    image : RImage
        Source ragged image.
    indices : array-like
        Pixel indices to retain.
    coordinates : array-like
        Replacement coordinates for retained pixels.

    Returns
    -------
    RImage
        Subset ragged image.
    """
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


def _warp_points(image, output_from_source, shape):
    """
    Transform sparse pixel coordinates and discard points outside a grid.

    Parameters
    ----------
    image : RImage, SImage, or DImage
        Point-based image data.
    output_from_source : Transform
        Mapping from source pixels to output pixels.
    shape : tuple of int
        Output ``(height, width)``.

    Returns
    -------
    RImage, SImage, or DImage
        Reindexed image using the same storage representation.
    """
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
    image,
    source_from_output,
    shape,
    interpolation='nearest',
    fill=0,
    mode='constant',
    frame_from_output=None,
    point_output_from_source=None,
):
    """
    Reindex spatial image data and update its reference frame.

    Parameters
    ----------
    image : SpatialImage
        Spatial image to reindex.
    source_from_output : Transform
        Mapping used to sample raster data.
    shape : tuple of int
        Output ``(height, width)``.
    interpolation : str, default='nearest'
        Raster interpolation mode.
    fill : scalar or sequence, default=0
        Fill values outside the source extent.
    mode : str, default='constant'
        SciPy boundary mode.
    frame_from_output : Transform, optional
        Alternate mapping used to update the spatial frame.
    point_output_from_source : Transform, optional
        Alternate forward mapping for point-based image data.

    Returns
    -------
    SpatialImage
        Reindexed image and updated geometry.
    """
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


def _restore(original, result):
    """
    Restore a transformed value to its original wrapped or bare form.
    """
    return result if isinstance(original, SpatialImage) else result.data


def _apply_local(image, operation):
    """
    Apply a local spatial operation to one image or both pair members.
    """
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
    def __init__(self, p=0.5, seed=None):
        """
        Initialize random horizontal flipping.

        Parameters
        ----------
        p : float, default=0.5
            Probability of flipping a sample.
        seed : int, optional
            Base random seed.
        """
        if not 0 <= p <= 1:
            raise ValueError('Probability must be between zero and one.')
        self.p = p
        self._init_random(seed)

    def __call__(self, image):
        """
        Randomly flip one image or both members of a pair horizontally.
        """
        if self._rng().random() >= self.p:
            return image

        def flip(spatial):
            """
            Flip one spatial image horizontally.
            """
            width = spatial.geometry.width
            mapping = Transform([[-1, 0, width - 1], [0, 1, 0], [0, 0, 1]])
            return _reindex_spatial(spatial, mapping, (spatial.geometry.height, width))

        return _apply_local(image, flip)


class RandomVerticalFlip(ImageTransform, WorkerRandomMixin):
    def __init__(self, p=0.5, seed=None):
        """
        Initialize random vertical flipping.

        Parameters
        ----------
        p : float, default=0.5
            Probability of flipping a sample.
        seed : int, optional
            Base random seed.
        """
        if not 0 <= p <= 1:
            raise ValueError('Probability must be between zero and one.')
        self.p = p
        self._init_random(seed)

    def __call__(self, image):
        """
        Randomly flip one image or both members of a pair vertically.
        """
        if self._rng().random() >= self.p:
            return image

        def flip(spatial):
            """
            Flip one spatial image vertically.
            """
            height = spatial.geometry.height
            mapping = Transform([[1, 0, 0], [0, -1, height - 1], [0, 0, 1]])
            return _reindex_spatial(spatial, mapping, (height, spatial.geometry.width))

        return _apply_local(image, flip)


class RandomRotate90(ImageTransform, WorkerRandomMixin):
    def __init__(self, p=0.5, choices=(1, 2, 3), seed=None):
        """
        Initialize random right-angle rotation.

        Parameters
        ----------
        p : float, default=0.5
            Probability of rotating a sample.
        choices : sequence of int, default=(1, 2, 3)
            Candidate numbers of quarter turns.
        seed : int, optional
            Base random seed.
        """
        if not 0 <= p <= 1:
            raise ValueError('Probability must be between zero and one.')
        choices = tuple(int(choice) % 4 for choice in choices)
        if not choices:
            raise ValueError('At least one rotation choice is required.')
        self.p = p
        self.choices = choices
        self._init_random(seed)

    def __call__(self, image):
        """
        Rotate a sample by a randomly selected multiple of 90 degrees.
        """
        if self._rng().random() >= self.p:
            return image
        turns = int(self._rng().choice(self.choices))

        def rotate(spatial):
            """
            Rotate one spatial image by the selected quarter turns.
            """
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
    def __init__(self, size, mpp=None):
        """
        Initialize a centered spatial crop.

        Parameters
        ----------
        size : int or tuple of int
            Output ``(height, width)`` in pixels.
        mpp : float or tuple of float, optional
            Output microns per pixel.
        """
        super().__init__(size=size, mpp=mpp)

    def _sample_polygon(self, polygon):
        """
        Return the centroid of the feasible crop-origin polygon.
        """
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
    def __init__(self, padding, fill=0):
        """
        Initialize padding for an in-memory image.

        Parameters
        ----------
        padding : int or sequence of int
            Uniform padding, horizontal/vertical padding, or
            ``(left, top, right, bottom)`` padding.
        fill : scalar or sequence, default=0
            Fill value for raster data.
        """
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
        """
        Pad one image or both members of a pair.
        """
        left, top, right, bottom = self.padding

        def pad(spatial):
            """
            Pad one spatial image.
            """
            shape = (
                spatial.geometry.height + top + bottom,
                spatial.geometry.width + left + right,
            )
            mapping = Transform.translation(-left, -top)
            return _reindex_spatial(spatial, mapping, shape, fill=self.fill)

        return _apply_local(image, pad)


class Resize(ImageTransform):
    def __init__(self, size, interpolation='bilinear'):
        """
        Initialize image-grid resizing.

        Parameters
        ----------
        size : int or sequence of int
            Output ``(height, width)``.
        interpolation : {'nearest', 'bilinear', 'bicubic'}, default='bilinear'
            Raster interpolation mode.
        """
        self.size = _size(size)
        if interpolation not in _INTERPOLATION_ORDERS:
            raise ValueError(f'Unknown interpolation: {interpolation}')
        self.interpolation = interpolation

    def _resize(self, spatial, size=None):
        """
        Resize one spatial image to the configured or supplied shape.

        Parameters
        ----------
        spatial : SpatialImage
            Spatial image to resize.
        size : tuple of int, optional
            Override output ``(height, width)``.

        Returns
        -------
        SpatialImage
            Resized image with an updated spatial frame.
        """
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
        """
        Resize one image or both members of a pair.
        """
        return _apply_local(image, self._resize)


class Resample(Resize):
    def __init__(self, mpp, interpolation='bilinear'):
        """
        Initialize resampling at a target physical resolution.

        Parameters
        ----------
        mpp : float or sequence of float
            Target microns per pixel.
        interpolation : {'nearest', 'bilinear', 'bicubic'}, default='bilinear'
            Raster interpolation mode.
        """
        mpp = (mpp, mpp) if isinstance(mpp, (int, float)) else tuple(mpp)
        if len(mpp) != 2 or any(value <= 0 for value in mpp):
            raise ValueError('Resolution must contain two positive values.')
        self.mpp = np.asarray(mpp, dtype=np.float64)
        self.interpolation = interpolation
        if interpolation not in _INTERPOLATION_ORDERS:
            raise ValueError(f'Unknown interpolation: {interpolation}')

    def __call__(self, image):
        """
        Resample an image while preserving its physical field of view.
        """
        def resample(spatial):
            """
            Resample one spatial image.
            """
            width = max(1, round(spatial.geometry.width * spatial.geometry.mpp[0] / self.mpp[0]))
            height = max(1, round(spatial.geometry.height * spatial.geometry.mpp[1] / self.mpp[1]))
            return self._resize(spatial, (height, width))

        return _apply_local(image, resample)


class RandomResizedCrop(ImageTransform, WorkerRandomMixin):
    def __init__(
        self,
        size,
        scale=(0.08, 1.0),
        ratio=(3 / 4, 4 / 3),
        seed=None,
    ):
        """
        Initialize random crop-and-resize augmentation.

        Parameters
        ----------
        size : int or sequence of int
            Output ``(height, width)``.
        scale : tuple of float, default=(0.08, 1.0)
            Range of overlap-area fractions to crop.
        ratio : tuple of float, default=(0.75, 1.333...)
            Range of crop aspect ratios.
        seed : int, optional
            Base random seed.
        """
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
        """
        Return the physical overlap dimensions available for cropping.
        """
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
        """
        Crop a random physical field and rasterize it to a fixed size.
        """
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
    def __init__(
        self,
        degrees,
        translate=None,
        scale=None,
        shear=None,
        interpolation='nearest',
        fill=0,
        seed=None,
    ):
        """
        Initialize random affine augmentation.

        Parameters
        ----------
        degrees : float or tuple of float
            Rotation range in degrees.
        translate : tuple of float, optional
            Maximum horizontal and vertical translation fractions.
        scale : float or tuple of float, optional
            Isotropic scale range.
        shear : float or sequence of float, optional
            Horizontal and optional vertical shear ranges in degrees.
        interpolation : {'nearest', 'bilinear', 'bicubic'}, default='nearest'
            Raster interpolation mode.
        fill : scalar or sequence, default=0
            Fill value outside the source extent.
        seed : int, optional
            Base random seed.
        """
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
        """
        Normalize and validate a scalar or two-value range.
        """
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
        """
        Apply a sampled affine transform to one image or a pair.
        """
        angle = np.deg2rad(self._rng().uniform(*self.degrees))
        scale = 1.0 if self.scale is None else self._rng().uniform(*self.scale)
        shear_x = np.deg2rad(self._rng().uniform(*self.shear[:2]))
        shear_y = np.deg2rad(self._rng().uniform(*self.shear[2:]))
        translation = (0.0, 0.0) if self.translate is None else (
            self._rng().uniform(-self.translate[0], self.translate[0]),
            self._rng().uniform(-self.translate[1], self.translate[1]),
        )

        def affine(spatial):
            """
            Apply the sampled affine transform to one spatial image.
            """
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
