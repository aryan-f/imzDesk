from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import time

import numpy as np
import pytest
from fastapi import HTTPException

import imzdesk.server.routes.images.msi as route_module
from imzdesk.core import DImage
from imzdesk.server.schema.images.msi import MSIImageRequest


def test_image_pipeline_forwards_server_batch_size_to_embedding(tmp_path, monkeypatch):
    captured = {}

    class FakeMSI:
        def derived_path(self, suffix):
            return tmp_path / f'sample{suffix}'

    class FakeEmbed:
        def __init__(self, model, batch_size):
            captured['model'] = model
            captured['batch_size'] = batch_size

    class FakeCompose:
        def __init__(self, transforms):
            captured['transforms'] = transforms

        def __call__(self, image):
            return DImage(
                values=np.array([1.0]),
                coordinates=np.array([[0, 0]]),
            )

    class FakeDisplay:
        def __init__(self, image, colormap):
            captured['colormap'] = colormap

        def save(self, path, format):
            Path(path).write_bytes(b'png')

    monkeypatch.setattr(route_module, 'get_msi_instance', lambda filepath: FakeMSI())
    monkeypatch.setattr(route_module.T, 'Embed', FakeEmbed)
    monkeypatch.setattr(route_module.T, 'Compose', FakeCompose)
    monkeypatch.setattr(route_module, 'DImageDisplay', FakeDisplay)
    settings = MSIImageRequest(
        filepath='sample.imzML',
        cubing={
            'method': 'embed',
            'model': 'roman-bushuiev/DreaMS',
        },
    )

    response = route_module.image_impl.__wrapped__(
        tmp_path / 'sample.imzML',
        settings,
        37,
    )

    assert response.media_type == 'image/png'
    assert captured['model'] == 'roman-bushuiev/DreaMS'
    assert captured['batch_size'] == 37


class FakeSpectrumMSI:
    coordinates = np.array([[4, 7], [6, 8]])

    def __init__(self):
        self.opened = False
        self.requested = None

    def __enter__(self):
        self.opened = True
        return self

    def __exit__(self, *_):
        self.opened = False

    def at(self, x, y):
        assert self.opened
        self.requested = (x, y)
        if self.requested != (6, 8):
            raise ValueError('missing')
        return np.array([100.25, 200.5]), np.array([12, 34], dtype=np.float32)


def test_spectrum_maps_rendered_pixel_to_native_msi_coordinate(tmp_path, monkeypatch):
    msi = FakeSpectrumMSI()
    monkeypatch.setattr(route_module, 'get_msi_instance', lambda filepath: msi)

    response = route_module.spectrum_impl.__wrapped__(tmp_path / 'sample.imzML', 2, 1)

    assert msi.requested == (6, 8)
    assert response == {
        'pixel': {'x': 2, 'y': 1},
        'coordinate': {'x': 6, 'y': 8},
        'mz': [100.25, 200.5],
        'intensities': [12.0, 34.0],
    }


@pytest.mark.parametrize(('x', 'y'), [(-1, 0), (0, -1), (0, 0)])
def test_spectrum_rejects_invalid_or_unmeasured_pixels(tmp_path, monkeypatch, x, y):
    monkeypatch.setattr(route_module, 'get_msi_instance', lambda filepath: FakeSpectrumMSI())

    with pytest.raises(HTTPException) as error:
        route_module.spectrum_impl.__wrapped__(tmp_path / 'sample.imzML', x, y)

    assert error.value.status_code == 404


def test_spectrum_rejects_msi_without_spatial_coordinates(tmp_path, monkeypatch):
    msi = FakeSpectrumMSI()
    msi.coordinates = np.empty((0, 2), dtype=np.int64)
    monkeypatch.setattr(route_module, 'get_msi_instance', lambda filepath: msi)

    with pytest.raises(HTTPException) as error:
        route_module.spectrum_impl.__wrapped__(tmp_path / 'sample.imzML', 0, 0)

    assert error.value.status_code == 404
    assert error.value.detail == 'The MSI does not contain spatial coordinates.'


def test_spectrum_serializes_reads_from_cached_msi_instance(tmp_path, monkeypatch):
    class ConcurrentSpectrumMSI(FakeSpectrumMSI):
        def __init__(self):
            super().__init__()
            self.active_reads = 0
            self.maximum_active_reads = 0

        def at(self, x, y):
            self.active_reads += 1
            self.maximum_active_reads = max(self.maximum_active_reads, self.active_reads)
            time.sleep(0.02)
            self.active_reads -= 1
            return np.array([100.0]), np.array([10.0])

    msi = ConcurrentSpectrumMSI()
    filepath = tmp_path / 'sample.imzML'
    monkeypatch.setattr(route_module, 'get_msi_instance', lambda path: msi)

    with ThreadPoolExecutor(max_workers=4) as executor:
        responses = list(executor.map(
            lambda _: route_module.spectrum_impl.__wrapped__(filepath, 2, 1),
            range(4),
        ))

    assert len(responses) == 4
    assert msi.maximum_active_reads == 1
