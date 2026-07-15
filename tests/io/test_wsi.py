import numpy as np
from PIL import Image

import imzdesk.io.wsi as wsi_module
from imzdesk.core import metadata
from imzdesk.io import WSI


class FakeOpenSlide:
    def __init__(self, filepath):
        self.filepath = filepath
        self.dimensions = (1000, 500)
        self.level_dimensions = [(1000, 500), (500, 250), (250, 125)]
        self.level_downsamples = [1.0, 2.0, 4.0]
        self.properties = {
            wsi_module.openslide.PROPERTY_NAME_MPP_X: '0.5',
            wsi_module.openslide.PROPERTY_NAME_MPP_Y: '1.0',
            wsi_module.openslide.PROPERTY_NAME_OBJECTIVE_POWER: '20',
            wsi_module.openslide.PROPERTY_NAME_VENDOR: 'FakeScope',
        }
        self.reads = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def read_region(self, location, level, size):
        self.reads.append((location, level, size))
        return Image.new('RGBA', size, (10, 20, 30, 255))


def test_wsi_init_metadata_reads_openslide_properties(monkeypatch, tmp_path):
    monkeypatch.setattr(wsi_module.openslide, 'OpenSlide', FakeOpenSlide)

    metadata = WSI.init_metadata(tmp_path / 'sample.ndpi')

    assert metadata.width == 1000
    assert metadata.height == 500
    assert metadata.vendor == 'FakeScope'
    assert metadata.objective_power == 20
    assert metadata.mpp == wsi_module.metadata.Dimensions(x=0.5, y=1.0)


def test_wsi_constructor_opens_slide(monkeypatch, tmp_path):
    monkeypatch.setattr(wsi_module.openslide, 'OpenSlide', FakeOpenSlide)

    image = WSI(tmp_path / 'sample.ndpi')

    assert isinstance(image.slide, FakeOpenSlide)


def test_wsi_to_image_applies_crop_at_selected_level(monkeypatch, tmp_path):
    monkeypatch.setattr(wsi_module.openslide, 'OpenSlide', FakeOpenSlide)
    image = WSI(tmp_path / 'sample.ndpi')
    image.metadata = wsi_module.WSIMetadata(
        width=1000,
        height=500,
        mpp=metadata.Dimensions(x=0.5, y=1.0),
        crop=metadata.BoundingBox(x=0.1, y=0.2, width=0.4, height=0.4),
    )

    raster = image.to_image(target_mpp=(1.0, 2.0), crop=True)

    assert raster.shape == (100, 200, 3)
    assert image.slide.reads == [((100, 100), 1, (200, 100))]


def test_wsi_to_image_resizes_axis_wise_target_mpp(monkeypatch, tmp_path):
    monkeypatch.setattr(wsi_module.openslide, 'OpenSlide', FakeOpenSlide)
    image = WSI(tmp_path / 'sample.ndpi')
    image.metadata = wsi_module.WSIMetadata(
        width=1000,
        height=500,
        mpp=metadata.Dimensions(x=0.5, y=1.0),
    )

    raster = image.to_image(target_mpp=(1.0, 4.0), crop=False)

    assert raster.shape == (125, 500, 3)
    assert image.slide.reads == [((0, 0), 1, (500, 250))]


def test_wsi_get_tile_forwards_deepzoom_coordinates(monkeypatch, tmp_path):
    monkeypatch.setattr(wsi_module.openslide, 'OpenSlide', FakeOpenSlide)
    image = WSI(tmp_path / 'sample.ndpi')

    class FakeDeepZoom:
        def get_tile(self, level, address):
            return level, address

    image.__dict__['deepzoom'] = FakeDeepZoom()

    assert image.get_tile(level=2, row=3, column=4) == (2, (4, 3))


def test_wsi_context_manager_returns_self(monkeypatch, tmp_path):
    monkeypatch.setattr(wsi_module.openslide, 'OpenSlide', FakeOpenSlide)
    image = WSI(tmp_path / 'sample.ndpi')

    with image as entered:
        assert entered is image
