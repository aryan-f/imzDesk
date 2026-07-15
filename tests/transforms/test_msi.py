from types import SimpleNamespace

import numpy as np
import pytest

import imzdesk.transforms as T
from imzdesk.core import RImage


class FakeMSI:
    def __init__(self, ibd_path, reader):
        self.ibd_path = ibd_path
        self.reader = reader

    def __len__(self):
        return len(self.reader.coordinates)

    @property
    def coordinates(self):
        return self.reader.coordinates


def test_to_rimage_reads_spectra_from_ibd_offsets(tmp_path):
    mz0 = np.array([50.0, 51.0], dtype=np.float64)
    mz1 = np.array([60.0], dtype=np.float64)
    intensity0 = np.array([1.0, 2.0], dtype=np.float32)
    intensity1 = np.array([3.0], dtype=np.float32)
    chunks = [mz0.tobytes(), intensity0.tobytes(), mz1.tobytes(), intensity1.tobytes()]
    offsets = []
    cursor = 0
    for chunk in chunks:
        offsets.append(cursor)
        cursor += len(chunk)
    ibd_path = tmp_path / 'sample.ibd'
    ibd_path.write_bytes(b''.join(chunks))
    reader = SimpleNamespace(
        coordinates=np.array([[0, 0], [1, 0]]),
        mzPrecision=np.dtype(np.float64),
        intensityPrecision=np.dtype(np.float32),
        mzOffsets=[offsets[0], offsets[2]],
        mzLengths=[2, 1],
        intensityOffsets=[offsets[1], offsets[3]],
        intensityLengths=[2, 1],
    )

    image = T.ToRImage()(FakeMSI(ibd_path, reader))

    assert isinstance(image, RImage)
    np.testing.assert_array_equal(image.coordinates, [[0, 0], [1, 0]])
    np.testing.assert_allclose(image.positions, [50.0, 51.0, 60.0])
    np.testing.assert_allclose(image.values, [1.0, 2.0, 3.0])
    np.testing.assert_array_equal(image.offsets, [0, 2, 3])


def test_spatial_coordinates_drops_constant_z_dimension():
    image = SimpleNamespace(coordinates=np.array([[1, 2, 5], [3, 4, 5]]))

    coordinates = T.ToRImage._spatial_coordinates(image)

    np.testing.assert_array_equal(coordinates, [[1, 2], [3, 4]])


def test_spatial_coordinates_rejects_varying_z_dimension():
    image = SimpleNamespace(coordinates=np.array([[1, 2, 5], [3, 4, 6]]))

    with pytest.raises(ValueError, match='z must be constant'):
        T.ToRImage._spatial_coordinates(image)


def test_spatial_coordinates_rejects_non_matrix_coordinates():
    image = SimpleNamespace(coordinates=np.array([1, 2, 3]))

    with pytest.raises(ValueError, match='2D array'):
        T.ToRImage._spatial_coordinates(image)


def test_spatial_coordinates_rejects_unsupported_dimension_count():
    image = SimpleNamespace(coordinates=np.zeros((2, 4)))

    with pytest.raises(ValueError, match='shape'):
        T.ToRImage._spatial_coordinates(image)


def test_embed_rejects_unknown_model():
    with pytest.raises(AssertionError, match='Unknown model'):
        T.Embed(model='unknown')
