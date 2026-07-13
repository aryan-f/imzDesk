from PIL import Image

from imzdesk.io import WSI
from imzdesk.transforms.base import Transform


class ToImage(Transform):

    def __init__(self, target_mpp: float):
        """
        Read a whole-slide image as a Pillow image near a target resolution.

        Parameters
        ----------
        target_mpp:
            Target microns per pixel.

        Attributes
        ----------
        target_mpp: float
            Target microns per pixel.
        """
        self.target_mpp = target_mpp

    def __call__(self, image: WSI) -> Image.Image:
        native_mpp = (image.metadata.mpp.x + image.metadata.mpp.y) / 2
        downsample = self.target_mpp / native_mpp
        level = image.slide.get_best_level_for_downsample(downsample)
        width, height = image.slide.level_dimensions[level]
        return image.slide.read_region((0, 0), level, (width, height)).convert('RGB')
