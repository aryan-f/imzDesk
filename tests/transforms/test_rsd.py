import numpy as np
from scipy import sparse

import imzdesk.transforms as T
import imzdesk.transforms.rsd as rsd_module
from imzdesk.core import DImage, RImage, SImage


def ragged_image():
    return RImage(
        coordinates=np.array([[0, 0], [1, 0], [0, 1]]),
        positions=np.array([50.0, 50.5, 51.2, 50.2, 52.0, 50.4]),
        values=np.array([1.0, 3.0, 6.0, 2.0, 8.0, 4.0], dtype=np.float32),
        offsets=np.array([0, 3, 5, 6]),
    )


def test_compose_applies_transforms_in_order():
    image = ragged_image()
    transform = T.Compose([
        T.Normalize('tic'),
        T.Bin(minimum_channel=50, maximum_channel=53, bin_width=1),
        T.TIC(),
    ])

    result = transform(image)

    assert isinstance(result, DImage)
    np.testing.assert_allclose(result.values, [1, 1, 1])


def test_normalize_none_returns_copy_of_values():
    image = ragged_image()

    normalized = T.Normalize('none')(image)

    assert normalized is not image
    assert normalized.values is not image.values
    np.testing.assert_allclose(normalized.values, image.values)


def test_normalize_tic_normalizes_each_pixel_sum():
    normalized = T.Normalize('tic')(ragged_image())

    np.testing.assert_allclose(normalized.values[:3].sum(), 1)
    np.testing.assert_allclose(normalized.values[3:5].sum(), 1)
    np.testing.assert_allclose(normalized.values[5:6].sum(), 1)


def test_normalize_log1p_applies_elementwise_transform():
    image = ragged_image()

    normalized = T.Normalize('log1p')(image)

    np.testing.assert_allclose(normalized.values, np.log1p(image.values))


def test_normalize_rms_median_max_and_zero_values():
    image = RImage(
        coordinates=np.array([[0, 0], [1, 0]]),
        positions=np.array([1.0, 2.0, 3.0]),
        values=np.array([3.0, 4.0, 0.0], dtype=np.float32),
        offsets=np.array([0, 2, 3]),
    )

    rms = T.Normalize('rms')(image)
    median = T.Normalize('median')(image)
    maximum = T.Normalize('max')(image)

    np.testing.assert_allclose(rms.values[:2], [3.0, 4.0] / np.sqrt(12.5))
    np.testing.assert_allclose(median.values[:2], np.array([3.0, 4.0]) / 3.5)
    np.testing.assert_allclose(maximum.values[:2], [0.75, 1.0])
    np.testing.assert_allclose(maximum.values[2], 0.0)


def test_normalize_skips_empty_pixel_segments():
    image = RImage(
        coordinates=np.array([[0, 0], [1, 0]]),
        positions=np.array([1.0]),
        values=np.array([2.0], dtype=np.float32),
        offsets=np.array([0, 0, 1]),
    )

    normalized = T.Normalize('tic')(image)

    np.testing.assert_allclose(normalized.values, [1.0])


def test_bin_sums_values_in_shared_channel_bins():
    image = ragged_image()

    binned = T.Bin(minimum_channel=50, maximum_channel=53, bin_width=1)(image)

    assert isinstance(binned, SImage)
    assert binned.values.shape == (3, 3)
    np.testing.assert_allclose(
        binned.values.toarray(),
        [
            [4, 6, 0],
            [2, 0, 8],
            [4, 0, 0],
        ],
    )
    np.testing.assert_array_equal(binned.coordinates, image.coordinates)


def test_bin_skips_pixels_without_positions_in_channel_range():
    image = RImage(
        coordinates=np.array([[0, 0], [1, 0]]),
        positions=np.array([10.0, 50.0]),
        values=np.array([7.0, 2.0], dtype=np.float32),
        offsets=np.array([0, 1, 2]),
    )

    binned = T.Bin(minimum_channel=50, maximum_channel=51, bin_width=1)(image)

    np.testing.assert_allclose(binned.values.toarray(), [[0], [2]])


def test_to_dense_converts_sparse_image_and_preserves_dense_image():
    sparse_image = SImage(
        values=sparse.csr_matrix([[1, 0], [0, 2]], dtype=np.float32),
        coordinates=np.array([[0, 0], [1, 0]]),
    )
    dense_image = T.ToDense()(sparse_image)

    assert isinstance(dense_image, DImage)
    np.testing.assert_allclose(dense_image.values, [[1, 0], [0, 2]])
    assert T.ToDense()(dense_image) is dense_image


def test_tic_sums_sparse_rows():
    sparse_image = SImage(
        values=sparse.csr_matrix([[1, 0, 2], [0, 3, 4]], dtype=np.float32),
        coordinates=np.array([[0, 0], [1, 0]]),
    )

    result = T.TIC()(sparse_image)

    np.testing.assert_allclose(result.values, [3, 7])
    np.testing.assert_array_equal(result.coordinates, sparse_image.coordinates)


def test_pca_returns_requested_components():
    image = DImage(
        values=np.array([
            [1.0, 0.0, 1.0],
            [2.0, 1.0, 0.0],
            [3.0, 0.0, 2.0],
            [4.0, 1.0, 1.0],
        ]),
        coordinates=np.array([[0, 0], [1, 0], [0, 1], [1, 1]]),
    )

    result = T.PCA(number_of_components=2)(image)

    assert result.values.shape == (4, 2)
    np.testing.assert_array_equal(result.coordinates, image.coordinates)


def test_nmf_accepts_sparse_input():
    image = SImage(
        values=sparse.csr_matrix([
            [1.0, 0.0, 1.0],
            [2.0, 1.0, 0.0],
            [3.0, 0.0, 2.0],
            [4.0, 1.0, 1.0],
        ]),
        coordinates=np.array([[0, 0], [1, 0], [0, 1], [1, 1]]),
    )

    result = T.NMF(number_of_components=2)(image)

    assert result.values.shape == (4, 2)
    assert np.all(result.values >= 0)


def test_project_returns_scalar_projection():
    image = DImage(
        values=np.array([
            [0.0, 0.0],
            [1.0, 0.0],
            [2.0, 0.0],
            [3.0, 0.0],
        ]),
        coordinates=np.array([[0, 0], [1, 0], [0, 1], [1, 1]]),
    )

    result = T.Project(number_of_components=1)(image)

    assert result.values.shape == (4,)
    np.testing.assert_array_equal(result.coordinates, image.coordinates)


def test_project_uses_low_energy_background_when_corner_is_empty():
    image = DImage(
        values=np.array([
            [0.0, 0.0],
            [1.0, 0.0],
            [2.0, 0.0],
            [3.0, 0.0],
        ]),
        coordinates=np.array([[1, 0], [0, 1], [1, 1], [2, 2]]),
    )

    result = T.Project(number_of_components=1, background_fraction=-0.1)(image)

    assert result.values.shape == (4,)
    assert 0 <= result.values.min() <= result.values.max() <= 1


def test_project_flips_direction_when_background_scores_higher():
    image = DImage(
        values=np.array([
            [10.0, 0.0],
            [0.0, 0.0],
            [1.0, 0.0],
            [2.0, 0.0],
        ]),
        coordinates=np.array([[0, 0], [1, 0], [0, 1], [1, 1]]),
    )

    result = T.Project(number_of_components=1, tissue_fraction=0.25, background_fraction=0.1)(image)

    assert result.values[0] == 0


def test_tsne_returns_requested_components(monkeypatch):
    image = DImage(
        values=np.arange(40 * 35, dtype=np.float32).reshape(40, 35),
        coordinates=np.column_stack([np.arange(40), np.zeros(40, dtype=int)]),
    )

    class FakeTSNE:
        def __init__(self, n_components, **kwargs):
            self.n_components = n_components

        def fit_transform(self, values):
            return values[:, :self.n_components]

    monkeypatch.setattr(rsd_module.manifold, 'TSNE', FakeTSNE)

    result = T.TSNE(number_of_components=2)(image)

    assert result.values.shape == (40, 2)
    np.testing.assert_array_equal(result.coordinates, image.coordinates)
