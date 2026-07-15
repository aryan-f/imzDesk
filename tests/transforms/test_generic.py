import numpy as np

import imzdesk.transforms as T


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
