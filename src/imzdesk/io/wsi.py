import functools

import numpy as np
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

    def init_metadata(self):
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
        pass

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

    def to_image(self, target_mpp: float | tuple[float, float] | None = None, shape=None, crop: bool = True) -> np.ndarray:
        """
        Read the whole slide as a numpy image near a target resolution.

        Parameters
        ----------
        target_mpp:
            Target microns per pixel. A scalar applies to both axes. If
            omitted, the native WSI resolution is used.
        shape:
            Accepted for API symmetry with dense image containers.
        crop:
            Whether to restrict the read to ``metadata.crop`` when available.

        Returns
        -------
        image: np.ndarray
            RGB image with shape ``(height, width, 3)``.
        """
        native_mpp = np.array([self.metadata.mpp.x, self.metadata.mpp.y], dtype=np.float64)
        target_mpp = native_mpp if target_mpp is None else np.asarray(target_mpp if isinstance(target_mpp, tuple) else (target_mpp, target_mpp), dtype=np.float64)
        target_downsample = target_mpp / native_mpp
        level_downsamples = np.asarray(self.slide.level_downsamples, dtype=np.float64)
        level = np.flatnonzero(level_downsamples <= target_downsample.min())[-1] if (level_downsamples <= target_downsample.min()).any() else 0
        downsample = level_downsamples[level]
        if crop and self.metadata.crop is not None:
            slide_width, slide_height = self.slide.dimensions
            crop_box = self.metadata.crop
            level0_x = round(crop_box.x * slide_width)
            level0_y = round(crop_box.y * slide_height)
            level0_width = round(crop_box.width * slide_width)
            level0_height = round(crop_box.height * slide_height)
            width = round(level0_width / downsample)
            height = round(level0_height / downsample)
            location = (level0_x, level0_y)
        else:
            width, height = self.slide.level_dimensions[level]
            location = (0, 0)
        level_mpp = native_mpp * level_downsamples[level]
        output_width = round(width * level_mpp[0] / target_mpp[0])
        output_height = round(height * level_mpp[1] / target_mpp[1])
        image = self.slide.read_region(location, level, (width, height)).convert('RGB')
        if (output_width, output_height) != (width, height):
            image = image.resize((output_width, output_height), Image.Resampling.LANCZOS)
        return np.asarray(image)
