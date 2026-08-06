import numpy as np
from scipy import sparse

from imzdesk.core import DImage, RImage, SImage


def test_rimage_pixel_returns_segment():
    image = RImage(
        coordinates=np.array([[0, 0], [1, 0]]),
        positions=np.array([100.0, 101.0, 200.0]),
        values=np.array([1.0, 2.0, 3.0]),
        offsets=np.array([0, 2, 3]),
    )

    positions, values = image.pixel(1)

    assert len(image) == 2
    np.testing.assert_allclose(positions, [200.0])
    np.testing.assert_allclose(values, [3.0])


def test_simage_len_uses_coordinates():
    image = SImage(
        values=sparse.csr_matrix(np.ones((3, 4))),
        coordinates=np.array([[0, 0], [1, 0], [0, 1]]),
    )

    assert len(image) == 3


def test_dimage_to_image_rasterizes_scalar_values():
    image = DImage(
        values=np.array([1, 2, 3]),
        coordinates=np.array([[0, 0], [2, 0], [1, 1]]),
    )

    raster = image.to_image()

    np.testing.assert_array_equal(raster, [[1, 0, 2], [0, 3, 0]])


def test_dimage_to_image_rasterizes_multichannel_values_with_shape():
    image = DImage(
        values=np.array([[1, 10], [2, 20]]),
        coordinates=np.array([[1, 0], [0, 1]]),
    )

    raster = image.to_image(shape=(3, 3))

    assert raster.shape == (3, 3, 2)
    np.testing.assert_array_equal(raster[0, 1], [1, 10])
    np.testing.assert_array_equal(raster[1, 0], [2, 20])
    np.testing.assert_array_equal(raster[2, 2], [0, 0])


def test_dimage_to_image_interpolates_nearest_measured_pixel():
    image = DImage(
        values=np.array([[1, 10], [2, 20]]),
        coordinates=np.array([[0, 0], [3, 0]]),
    )

    raster = image.to_image(shape=(2, 4), interpolation='nearest')

    np.testing.assert_array_equal(raster, [
        [[1, 10], [1, 10], [2, 20], [2, 20]],
        [[1, 10], [1, 10], [2, 20], [2, 20]],
    ])


def test_dimage_to_image_nearest_preserves_empty_canvas():
    image = DImage(
        values=np.empty((0, 2)),
        coordinates=np.empty((0, 2), dtype=int),
    )

    raster = image.to_image(shape=(2, 3), interpolation='nearest')

    np.testing.assert_array_equal(raster, np.zeros((2, 3, 2)))


def test_dimage_to_image_rejects_unknown_interpolation():
    image = DImage(values=np.array([1]), coordinates=np.array([[0, 0]]))

    with np.testing.assert_raises_regex(ValueError, 'Unknown raster interpolation'):
        image.to_image(interpolation='linear')
