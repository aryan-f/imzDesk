from imzdesk.core import DImage
from imzdesk.io import WSI
from imzdesk.transforms.base import Transform


class ToImage(Transform):
    def __init__(
        self,
        target_mpp=None,
        shape=None,
        crop=True,
        interpolation=None,
    ):
        """
        Initialize conversion from image-like objects to dense NumPy arrays.

        Parameters
        ----------
        target_mpp : float or tuple of float, optional
            Target microns per pixel for objects that support physical image
            scaling. A scalar applies to both axes.
        shape : tuple of int, optional
            Optional ``(height, width)`` output shape for rasterized data
            containers.
        crop : bool, default=True
            Whether image file classes should apply their metadata crop when
            one is available.
        interpolation : {None, 'nearest'}, optional
            Optional interpolation for dense data containers. ``'nearest'``
            fills unmeasured raster locations from the nearest measured pixel.

        """
        if interpolation not in (None, 'nearest'):
            raise ValueError(f'Unknown raster interpolation: {interpolation}')
        self.target_mpp = target_mpp
        self.shape = shape
        self.crop = crop
        self.interpolation = interpolation

    def __call__(self, image):
        """
        Convert an image-like object to a dense array.

        Parameters
        ----------
        image : DImage or WSI
            Image-like value to rasterize.

        Returns
        -------
        numpy.ndarray
            Rasterized image.
        """
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
