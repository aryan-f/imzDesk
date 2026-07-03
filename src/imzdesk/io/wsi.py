import functools

import openslide
import openslide.deepzoom
from PIL import Image

from .base import ImageBase
from ..core import metadata


class WSIMetadata(metadata.Metadata):
    vendor: str | None = None
    crop: metadata.BoundingBox | None = None
    tile_size: int = metadata.Field(default=254, ge=1)
    tile_overlap: int = metadata.Field(default=1, ge=0)
    objective_power: float | None = metadata.Field(default=None, gt=0)


class WSI(ImageBase):
    metadata_class = WSIMetadata
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
        return WSIMetadata(
            width=width,
            height=height,
            mpp=metadata.Dimensions(
                x=float(self.slide.properties[openslide.PROPERTY_NAME_MPP_X]),
                y=float(self.slide.properties[openslide.PROPERTY_NAME_MPP_Y]),
            ),
            objective_power=float(self.slide.properties[openslide.PROPERTY_NAME_OBJECTIVE_POWER]),
            vendor=self.slide.properties[openslide.PROPERTY_NAME_VENDOR],
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.write_metadata_to_disk()

    @functools.cached_property
    def deepzoom(self):
        return openslide.deepzoom.DeepZoomGenerator(
            self.slide,
            tile_size=self.metadata.tile_size,
            overlap=self.metadata.tile_overlap,
            limit_bounds=False,  # keeps the pyramid anchored to full level 0 dims, so world coordinates never shift.
        )

    def get_tile(self, level: int, row: int, column: int) -> Image.Image:
        return self.deepzoom.get_tile(level, (column, row))
