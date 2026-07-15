import numpy as np
import pytest

from imzdesk.core import RImage


pytestmark = [
    pytest.mark.requires_torch,
    pytest.mark.slow,
]


def test_dreams_preprocess_sorts_peaks_by_intensity():
    pytest.importorskip('torch')
    from imzdesk.transforms.models.dreams import DreaMS

    model = DreaMS(device='cpu')
    spectrum = model.preprocess((
        np.array([100.0, 200.0, 300.0]),
        np.array([2.0, 5.0, 3.0]),
    ))

    assert spectrum.shape == (model.network.top_n, 2)
    np.testing.assert_allclose(spectrum[:3].cpu().numpy(), [[200.0, 5.0], [300.0, 3.0], [100.0, 2.0]])


def test_dreams_embed_returns_dense_image():
    pytest.importorskip('torch')
    from imzdesk.transforms.models.dreams import DreaMS

    image = RImage(
        coordinates=np.array([[0, 0], [1, 0]]),
        positions=np.array([100.0, 200.0, 150.0, 250.0]),
        values=np.array([1.0, 5.0, 2.0, 3.0], dtype=np.float32),
        offsets=np.array([0, 2, 4]),
    )
    model = DreaMS(device='cpu')

    embedded = model.embed(image, batch_size=1)

    assert embedded.values.shape == (2, 1024)
    np.testing.assert_array_equal(embedded.coordinates, image.coordinates)
    assert np.isfinite(embedded.values).all()
