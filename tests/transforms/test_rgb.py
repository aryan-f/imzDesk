import numpy as np

import imzdesk.transforms as T


def test_optical_density_returns_normalized_scalar_density():
    image = np.array([
        [[255, 255, 255], [0, 0, 0]],
    ], dtype=np.uint8)

    density = T.OpticalDensity()(image)

    assert density.shape == (1, 2)
    np.testing.assert_allclose(density[0, 0], 0)
    np.testing.assert_allclose(density.max(), 1)


def test_threshold_returns_boolean_mask():
    image = np.array([
        [0.0, 0.1, 0.2],
        [0.8, 0.9, 1.0],
    ])

    mask = T.Threshold()(image)

    assert mask.dtype == bool
    assert mask.shape == image.shape
    assert mask[1, 2]


def test_threshold_averages_rgb_input_and_uses_fallback_for_degenerate_mask():
    image = np.ones((2, 2, 3), dtype=np.float32)

    mask = T.Threshold()(image)

    assert mask.shape == (2, 2)
    assert not mask.any()
