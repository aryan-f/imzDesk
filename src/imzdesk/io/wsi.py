from pathlib import Path

import openslide

from .base import I
from .meta import Dimensions


class WSI(I):

    def __init__(self, filepath, meta_path=None):
        """
        Whole Slide Image.

        The class is a wrapper on ``openslide.OpenSlide`` that provides some extra functionalities.

        Parameters
        ----------
        filepath: Path or str
            The path to a pathology image file supported by **OpenSlide**.
        meta_path: Path or str
            The path to the meta file. If not provided, it will be inferred from the file path.
        """
        super().__init__(filepath, meta_path)

        self.slide = openslide.OpenSlide(self.filepath)

        self.initialize_meta_if_needed()

    def initialize_meta_if_needed(self):
        if self.meta.width is None or self.meta.height is None:
            self.meta.width, self.meta.height = self.slide.dimensions
        if self.meta.mpp is None:
            self.meta.mpp = Dimensions(
                x=float(self.slide.properties[openslide.PROPERTY_NAME_MPP_X]),
                y=float(self.slide.properties[openslide.PROPERTY_NAME_MPP_Y]),
            )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.meta.to_file(self.meta_path)
