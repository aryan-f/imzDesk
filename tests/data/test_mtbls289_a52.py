from pathlib import Path

import numpy as np
import pytest

import imzdesk.transforms as T
import imzdesk.registration as R
from imzdesk.io import MSI, WSI


FIXTURE_DIR = Path(__file__).resolve().parents[2] / 'examples' / 'data' / 'MTBLS289' / 'A52 5cm S4'
MSI_PATH = FIXTURE_DIR / 'A52 5cm S4-profile.imzML'
WSI_PATH = FIXTURE_DIR / 'NICOLE A52 5CM 20.06.13 (4) - 2014-05-27 16.33.21.ndpi'


pytestmark = [
    pytest.mark.requires_data,
]


def require_fixture_files():
    if not MSI_PATH.exists() or not MSI_PATH.with_suffix('.ibd').exists() or not WSI_PATH.exists():
        pytest.skip('MTBLS289 A52 fixture files are not available.')


def test_a52_msi_metadata_initializes_from_imzml():
    require_fixture_files()

    metadata = MSI.init_metadata(MSI_PATH)

    assert metadata.width == 51
    assert metadata.height == 82
    assert metadata.mpp.x == 135
    assert metadata.mpp.y == 135
    assert metadata.size.x == 0.69
    assert metadata.size.y == 1.11


def test_a52_wsi_metadata_initializes_from_openslide():
    require_fixture_files()

    metadata = WSI.init_metadata(WSI_PATH)

    assert metadata.width == 135168
    assert metadata.height == 37120
    assert metadata.vendor == 'hamamatsu'
    assert metadata.objective_power == 40
    np.testing.assert_allclose([metadata.mpp.x, metadata.mpp.y], [0.22710240047237298, 0.2270972430394695])


def test_a52_msi_reads_first_spectrum_from_ibd():
    require_fixture_files()
    image = MSI(MSI_PATH, cache_portable=False)

    with image:
        mz, intensities = image[0]

    assert mz.ndim == 1
    assert intensities.ndim == 1
    assert mz.shape == intensities.shape
    assert mz.size > 0
    assert np.all(np.diff(mz) >= 0)
    assert intensities.max() > 0


def test_a52_wsi_to_image_reads_small_surrogate():
    require_fixture_files()
    image = WSI(WSI_PATH)
    image.metadata = WSI.init_metadata(WSI_PATH)

    surrogate = image.to_image(target_mpp=(200, 200), crop=False)

    assert surrogate.ndim == 3
    assert surrogate.shape[2] == 3
    assert surrogate.shape[0] > 0
    assert surrogate.shape[1] > 0


@pytest.mark.slow
def test_a52_to_rimage_matches_first_pyimzml_spectrum():
    require_fixture_files()
    image = MSI(MSI_PATH, cache_portable=False)

    with image:
        expected_mz, expected_intensities = image[0]
    ragged = T.ToRImage()(image)
    mz, intensities = ragged.pixel(0)

    np.testing.assert_allclose(mz, expected_mz)
    np.testing.assert_allclose(intensities, expected_intensities)


@pytest.mark.slow
@pytest.mark.requires_torch
def test_a52_registration_returns_finite_transform():
    pytest.importorskip('torch')
    require_fixture_files()
    wsi = WSI(WSI_PATH)
    source = MSI(MSI_PATH, cache_portable=False)
    metadata = MSI.init_metadata(MSI_PATH)

    class SubsetMSI:
        def __len__(self):
            return len(self.coordinates)

    msi = SubsetMSI()
    msi.ibd_path = source.ibd_path
    msi.reader = source.reader
    msi.coordinates = source.coordinates[:256]
    msi.metadata = metadata

    transform = R.register(wsi, msi)

    assert transform.matrix.shape == (3, 3)
    assert np.isfinite(transform.matrix).all()
    np.testing.assert_allclose(transform.matrix[2], [0, 0, 1])
