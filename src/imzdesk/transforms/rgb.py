import numpy as np
from PIL import Image

from imzdesk.transforms.base import Transform


class OpticalDensity(Transform):

    def __init__(self, white_level: float = 255.0):
        """
        Convert an RGB Pillow image to an optical-density grayscale image.

        Parameters
        ----------
        white_level:
            Reference white intensity used in ``-log(I / white_level)``.

        Attributes
        ----------
        white_level: float
            Reference white intensity.
        """
        self.white_level = white_level

    def __call__(self, image: Image.Image) -> Image.Image:
        pixels = np.asarray(image.convert('RGB'), dtype=np.float32)
        density = -np.log((pixels + 1.0) / (self.white_level + 1.0))
        density = density.mean(axis=2)
        density = density / density.max() if density.max() > 0 else density
        return Image.fromarray((density * 255).astype(np.uint8), mode='L')
