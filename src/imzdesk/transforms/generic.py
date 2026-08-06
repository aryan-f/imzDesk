import numpy as np

from imzdesk.core import DImage
from imzdesk.io import WSI
from imzdesk.transforms.base import Transform


class ToImage(Transform):
    def __init__(
        self,
        target_mpp: float | tuple[float, float] | None = None,
        shape: tuple[int, int] | None = None,
        crop: bool = True,
        interpolation: str | None = None,
    ):
        """
        Convert an image-like object to a dense numpy image.

        Parameters
        ----------
        target_mpp:
            Target microns per pixel for objects that support physical image
            scaling. A scalar applies to both axes.
        shape:
            Optional ``(height, width)`` output shape for rasterized data
            containers.
        crop:
            Whether image file classes should apply their metadata crop when
            one is available.
        interpolation:
            Optional interpolation for dense data containers. ``'nearest'``
            fills unmeasured raster locations from the nearest measured pixel.

        Attributes
        ----------
        target_mpp: float | tuple[float, float] | None
            Target microns per pixel.
        shape: tuple[int, int] | None
            Optional ``(height, width)`` output shape.
        crop: bool
            Whether metadata crop should be applied when supported.
        interpolation: str | None
            Raster interpolation for dense data containers.
        """
        if interpolation not in (None, 'nearest'):
            raise ValueError(f'Unknown raster interpolation: {interpolation}')
        self.target_mpp = target_mpp
        self.shape = shape
        self.crop = crop
        self.interpolation = interpolation

    def __call__(self, image: DImage | WSI) -> np.ndarray:
        if isinstance(image, DImage):
            return image.to_image(
                target_mpp=self.target_mpp,
                shape=self.shape,
                crop=self.crop,
                interpolation=self.interpolation,
            )
        if self.interpolation is not None:
            raise TypeError('ToImage interpolation is only supported for DImage inputs.')
        return image.to_image(target_mpp=self.target_mpp, shape=self.shape, crop=self.crop)
