from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from scipy import ndimage
from skimage import color

from imzdesk.core import PairedImage, SpatialImage
from imzdesk.transforms._random import WorkerRandomMixin
from imzdesk.transforms.base import Transform


def _torch():
    try:
        import torch
    except ImportError:
        return None
    return torch


def _map_data(image, operation):
    if isinstance(image, SpatialImage):
        return SpatialImage(operation(image.data), image.geometry, image.pixel_to_reference)
    return operation(image)


def _map_pair(image, operation):
    if isinstance(image, PairedImage):
        return PairedImage(
            _map_data(image.wsi, operation),
            _map_data(image.msi, operation),
            image.registration,
        )
    return _map_data(image, operation)


def _kernel_size(value) -> tuple[int, int]:
    values = (value, value) if isinstance(value, int) else tuple(value)
    if len(values) != 2 or any(item <= 0 or item % 2 == 0 for item in values):
        raise ValueError('Kernel size must contain two positive odd values.')
    return int(values[0]), int(values[1])


def _range(value, name, minimum=None, maximum=None, center=None):
    if isinstance(value, (int, float)):
        if value < 0:
            raise ValueError(f'{name} must be nonnegative.')
        values = (center - value, center + value) if center is not None else (float(value), float(value))
        if minimum is not None:
            values = (max(minimum, values[0]), values[1])
    else:
        if len(value) != 2:
            raise ValueError(f'{name} must be a number or contain two values.')
        values = tuple(float(item) for item in value)
    if (
        values[0] > values[1]
        or (minimum is not None and values[0] < minimum)
        or (maximum is not None and values[1] > maximum)
    ):
        raise ValueError(f'{name} contains an invalid range.')
    return values


class GaussianBlur(Transform, WorkerRandomMixin):
    """Blur raster data with a Gaussian kernel."""

    def __init__(self, kernel_size, sigma=(0.1, 2.0), seed: int | None = None):
        self.kernel_size = _kernel_size(kernel_size)
        self.sigma = _range(sigma, 'Sigma', minimum=np.finfo(float).eps)
        self._init_random(seed)

    def __call__(self, image):
        sigma = self._rng().uniform(*self.sigma)
        return _map_pair(image, lambda data: self._blur(data, sigma))

    def _blur(self, image, sigma):
        torch = _torch()
        if torch is not None and isinstance(image, torch.Tensor):
            return self._blur_tensor(image, sigma, torch)
        if not isinstance(image, np.ndarray) or image.ndim not in (2, 3):
            raise TypeError('GaussianBlur expects a 2D or channel-last 3D raster.')
        radius = (self.kernel_size[0] // 2, self.kernel_size[1] // 2)
        values = image.astype(np.float32, copy=False)
        if image.ndim == 2:
            result = ndimage.gaussian_filter(values, sigma=(sigma, sigma), radius=radius)
        else:
            result = ndimage.gaussian_filter(
                values,
                sigma=(sigma, sigma, 0),
                radius=(*radius, 0),
            )
        if np.issubdtype(image.dtype, np.integer):
            limits = np.iinfo(image.dtype)
            return np.rint(np.clip(result, limits.min, limits.max)).astype(image.dtype)
        return result.astype(image.dtype, copy=False)

    def _blur_tensor(self, image, sigma, torch):
        import torch.nn.functional as functional

        if image.ndim not in (2, 3):
            raise TypeError('GaussianBlur expects a 2D or channel-first 3D tensor.')
        source = image[None, None] if image.ndim == 2 else image[None]
        source_dtype = source.dtype
        source = source.float()
        y = torch.arange(self.kernel_size[0], device=image.device, dtype=source.dtype)
        x = torch.arange(self.kernel_size[1], device=image.device, dtype=source.dtype)
        y = y - (self.kernel_size[0] - 1) / 2
        x = x - (self.kernel_size[1] - 1) / 2
        kernel = torch.exp(-(y[:, None] ** 2 + x[None, :] ** 2) / (2 * sigma ** 2))
        kernel = kernel / kernel.sum()
        kernel = kernel.expand(source.shape[1], 1, *kernel.shape)
        padding = (self.kernel_size[1] // 2, self.kernel_size[1] // 2,
                   self.kernel_size[0] // 2, self.kernel_size[0] // 2)
        result = functional.conv2d(
            functional.pad(source, padding, mode='reflect'),
            kernel,
            groups=source.shape[1],
        )
        result = result[0, 0] if image.ndim == 2 else result[0]
        return result.to(source_dtype)


class ColorJitter(Transform, WorkerRandomMixin):
    """Randomly jitter WSI brightness, contrast, saturation, and hue."""

    def __init__(
        self,
        brightness=0,
        contrast=0,
        saturation=0,
        hue=0,
        seed: int | None = None,
    ):
        self.brightness = _range(brightness, 'Brightness', minimum=0, center=1)
        self.contrast = _range(contrast, 'Contrast', minimum=0, center=1)
        self.saturation = _range(saturation, 'Saturation', minimum=0, center=1)
        self.hue = _range(hue, 'Hue', minimum=-0.5, maximum=0.5, center=0)
        self._init_random(seed)

    def __call__(self, image):
        parameters = {
            'brightness': self._rng().uniform(*self.brightness),
            'contrast': self._rng().uniform(*self.contrast),
            'saturation': self._rng().uniform(*self.saturation),
            'hue': self._rng().uniform(*self.hue),
        }
        order = self._rng().permutation(tuple(parameters))

        def jitter(data):
            if not isinstance(data, np.ndarray) or data.ndim != 3 or data.shape[2] != 3:
                raise TypeError('ColorJitter expects a channel-last RGB NumPy image.')
            original_dtype = data.dtype
            maximum = np.iinfo(original_dtype).max if np.issubdtype(original_dtype, np.integer) else 1.0
            values = data.astype(np.float32) / maximum
            for operation in order:
                factor = parameters[operation]
                if operation == 'brightness':
                    values = values * factor
                elif operation == 'contrast':
                    gray_mean = color.rgb2gray(np.clip(values, 0, 1)).mean()
                    values = gray_mean + factor * (values - gray_mean)
                elif operation == 'saturation':
                    gray = color.rgb2gray(np.clip(values, 0, 1))[..., None]
                    values = gray + factor * (values - gray)
                else:
                    hsv = color.rgb2hsv(np.clip(values, 0, 1))
                    hsv[..., 0] = (hsv[..., 0] + factor) % 1
                    values = color.hsv2rgb(hsv)
            values = np.clip(values, 0, 1) * maximum
            if np.issubdtype(original_dtype, np.integer):
                values = np.rint(values)
            return values.astype(original_dtype)

        if isinstance(image, PairedImage):
            return PairedImage(_map_data(image.wsi, jitter), image.msi, image.registration)
        return _map_data(image, jitter)


class RandomErasing(Transform, WorkerRandomMixin):
    """Erase a random raster region, sharing normalized bounds across a pair."""

    def __init__(
        self,
        p: float = 0.5,
        scale=(0.02, 0.33),
        ratio=(0.3, 3.3),
        value=0,
        seed: int | None = None,
    ):
        if not 0 <= p <= 1:
            raise ValueError('Probability must be between zero and one.')
        if len(scale) != 2 or scale[0] < 0 or scale[0] > scale[1] or scale[1] > 1:
            raise ValueError('Scale must be an increasing pair between zero and one.')
        if len(ratio) != 2 or ratio[0] <= 0 or ratio[0] > ratio[1]:
            raise ValueError('Ratio must contain an increasing pair of positive values.')
        self.p = p
        self.scale = tuple(scale)
        self.ratio = tuple(ratio)
        self.value = value
        self._init_random(seed)

    def __call__(self, image):
        if self._rng().random() >= self.p:
            return image
        area = self._rng().uniform(*self.scale)
        aspect = np.exp(self._rng().uniform(*np.log(self.ratio)))
        vertical = self._rng().random()
        horizontal = self._rng().random()
        return _map_pair(
            image,
            lambda data: self._erase(data, area, aspect, vertical, horizontal),
        )

    def _erase(self, image, area_fraction, aspect, vertical, horizontal):
        torch = _torch()
        tensor = torch is not None and isinstance(image, torch.Tensor)
        if tensor:
            if image.ndim not in (2, 3):
                raise TypeError('RandomErasing expects a 2D or channel-first 3D tensor.')
            height, width = image.shape[-2:]
        elif isinstance(image, np.ndarray) and image.ndim in (2, 3):
            height, width = image.shape[:2]
        else:
            raise TypeError('RandomErasing expects a 2D or 3D raster.')

        erase_height = min(height, max(1, round(np.sqrt(area_fraction * height * width / aspect))))
        erase_width = min(width, max(1, round(np.sqrt(area_fraction * height * width * aspect))))
        top = round(vertical * (height - erase_height))
        left = round(horizontal * (width - erase_width))
        result = image.clone() if tensor else image.copy()
        value = self._value_for(image, tensor, torch)
        if tensor:
            result[..., top:top + erase_height, left:left + erase_width] = value
        else:
            result[top:top + erase_height, left:left + erase_width, ...] = value
        return result

    def _value_for(self, image, tensor, torch):
        if np.isscalar(self.value):
            return self.value
        channels = 1 if image.ndim == 2 else image.shape[0 if tensor else 2]
        values = tuple(self.value)
        if len(values) not in (1, channels):
            raise ValueError(f'Expected one or {channels} erase values.')
        if image.ndim == 2:
            return values[0]
        if tensor:
            return torch.as_tensor(values, dtype=image.dtype, device=image.device)[:, None, None]
        return np.asarray(values, dtype=image.dtype)


class ChannelNormalize(Transform):
    """Normalize raster channels with fixed means and standard deviations."""

    def __init__(self, mean, std):
        self.mean = np.atleast_1d(np.asarray(mean, dtype=np.float64))
        self.std = np.atleast_1d(np.asarray(std, dtype=np.float64))
        if len(self.mean) != len(self.std) or np.any(self.std <= 0):
            raise ValueError('Mean and standard deviation must have equal lengths and positive deviations.')

    def __call__(self, image):
        return _map_pair(image, self._normalize)

    def _normalize(self, image):
        torch = _torch()
        if torch is not None and isinstance(image, torch.Tensor):
            values = image if torch.is_floating_point(image) else image.float()
            if image.ndim == 2:
                if len(self.mean) != 1:
                    raise ValueError('Expected one normalization value.')
                mean = torch.as_tensor(self.mean, dtype=values.dtype, device=image.device)[:, None, None]
                std = torch.as_tensor(self.std, dtype=values.dtype, device=image.device)[:, None, None]
                result = (values[None] - mean) / std
                return result[0]
            if image.ndim != 3:
                raise TypeError('ChannelNormalize expects a 2D or channel-first 3D tensor.')
            channels = image.shape[0]
            mean = torch.as_tensor(self.mean, dtype=values.dtype, device=image.device)[:, None, None]
            std = torch.as_tensor(self.std, dtype=values.dtype, device=image.device)[:, None, None]
            if len(mean) not in (1, channels):
                raise ValueError(f'Expected one or {channels} normalization values.')
            return (values - mean) / std

        if not isinstance(image, np.ndarray) or image.ndim not in (2, 3):
            raise TypeError('ChannelNormalize expects a 2D or channel-last 3D raster.')
        values = image if np.issubdtype(image.dtype, np.floating) else image.astype(np.float32)
        channels = 1 if image.ndim == 2 else image.shape[2]
        if len(self.mean) not in (1, channels):
            raise ValueError(f'Expected one or {channels} normalization values.')
        mean = self.mean.astype(values.dtype, copy=False)
        std = self.std.astype(values.dtype, copy=False)
        if image.ndim == 2:
            return (values - mean[0]) / std[0]
        return (values - mean) / std
