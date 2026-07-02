from pathlib import Path

import openslide

from .base import Image
from ..core import metadata


class WSI(Image):
    metadata_class = metadata.WSIMetadata
    extensions = ('.svs', '.avs', '.dcm', '.vms', '.vmu', '.ndpi', '.tif', '.scn', '.mrxs', '.tiff', '.svslide', '.bif')  # See https://openslide.org/formats/.

    def __init__(self, filepath):
        """
        Whole Slide Image.

        The class is a wrapper on ``openslide.OpenSlide`` that provides some extra functionalities.

        Parameters
        ----------
        filepath: Path or str
            The path to a pathology image file supported by **OpenSlide**.
        """
        super().__init__(filepath)
        self.slide = openslide.OpenSlide(self.filepath)
        self.resolve_metadata()

    def initialize_metadata(self):
        width, height = self.slide.dimensions
        return metadata.WSIMetadata(
            width=width,
            height=height,
            mpp=metadata.Dimensions(
                x=float(self.slide.properties[openslide.PROPERTY_NAME_MPP_X]),
                y=float(self.slide.properties[openslide.PROPERTY_NAME_MPP_Y]),
            )
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.write_metadata_to_disk()
