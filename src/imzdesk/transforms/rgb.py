import numpy as np
from skimage.filters import threshold_otsu

from imzdesk.transforms.base import Transform


class OpticalDensity(Transform):

    def __init__(self, white_level=255.0):
        """
        Convert an RGB image array to normalized optical density.

        Parameters
        ----------
        white_level : float, default=255.0
            Reference white intensity used in ``-log(I / white_level)``.

        """
        self.white_level = white_level

    def __call__(self, image):
        """
        Convert an RGB image to normalized scalar optical density.

        Parameters
        ----------
        image : array-like
            RGB image.

        Returns
        -------
        numpy.ndarray
            Normalized scalar optical-density image.
        """
        pixels = np.asarray(image, dtype=np.float32)
        density = -np.log((pixels + 1.0) / (self.white_level + 1.0))
        if density.ndim == 3:
            density = density.mean(axis=2)
        density = density / density.max() if density.max() > 0 else density
        return density.astype(np.float32)


class Threshold(Transform):

    def __init__(self, fallback_percentile=75.0):
        """
        Threshold a scalar image into a boolean mask.

        Parameters
        ----------
        fallback_percentile : float, default=75.0
            Percentile used when Otsu returns a degenerate mask.
        """
        self.fallback_percentile = fallback_percentile

    def __call__(self, image):
        """
        Threshold a scalar image into a boolean foreground mask.

        Parameters
        ----------
        image : array-like
            Scalar or multichannel image.

        Returns
        -------
        numpy.ndarray
            Boolean foreground mask.
        """
        values = np.asarray(image, dtype=np.float32)
        if values.ndim == 3:
            values = values.mean(axis=2)
        threshold = threshold_otsu(values)
        mask = values > threshold
        foreground_fraction = mask.mean()
        if foreground_fraction <= 0.01 or foreground_fraction >= 0.99:
            mask = values > np.percentile(values, self.fallback_percentile)
        return mask
