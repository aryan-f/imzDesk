import numpy as np

import imzdesk.transforms as T
from imzdesk.core import DImage


class ImageLike:
    def __init__(self):
        self.calls = []

    def to_image(self, target_mpp=None, shape=None, crop=True):
        self.calls.append((target_mpp, shape, crop))
        return np.zeros((2, 3), dtype=np.uint8)


def test_to_image_forwards_target_shape_and_crop():
    image = ImageLike()
    transform = T.ToImage(target_mpp=(1.0, 2.0), shape=(2, 3), crop=False)

    result = transform(image)

    assert result.shape == (2, 3)
    assert image.calls == [((1.0, 2.0), (2, 3), False)]


def test_to_image_applies_nearest_interpolation_to_dense_image():
    image = DImage(
        values=np.array([1, 2]),
        coordinates=np.array([[0, 0], [3, 0]]),
    )

    result = T.ToImage(shape=(2, 4), interpolation='nearest')(image)

    np.testing.assert_array_equal(result, [
        [1, 1, 2, 2],
        [1, 1, 2, 2],
    ])


def test_to_image_rejects_interpolation_for_file_image():
    with np.testing.assert_raises_regex(TypeError, 'only supported for DImage'):
        T.ToImage(interpolation='nearest')(ImageLike())


def test_to_image_rejects_unknown_interpolation():
    with np.testing.assert_raises_regex(ValueError, 'Unknown raster interpolation'):
        T.ToImage(interpolation='linear')
