from pathlib import Path

import numpy as np

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
