from types import SimpleNamespace

import numpy as np
import pytest
from scipy import sparse

import imzdesk.transforms as T
import imzdesk.transforms.geometry as geometry_module
import imzdesk.transforms.msi as msi_module
import imzdesk.transforms.spatial as spatial_module
from imzdesk.core import DImage, Geometry, PairedImage, RImage, SImage, SpatialImage, Transform


def spatial(values, mpp=1, frame=None):
    height, width = values.shape[:2]
    frame = Transform.scale(mpp) if frame is None else frame
    return SpatialImage(
        values,
        Geometry(width=width, height=height, mpp=mpp),
        frame,
    )


def test_random_horizontal_flip_is_exact_for_array():
    image = np.arange(6).reshape(2, 3)

    result = T.RandomHorizontalFlip(p=1, seed=0)(image)

    np.testing.assert_array_equal(result, np.fliplr(image))


def test_random_horizontal_flip_updates_frame_and_pair_registration():
    source = spatial(np.arange(6).reshape(2, 3), mpp=2)
    pair = PairedImage(source, source, Transform.identity())

    result = T.RandomHorizontalFlip(p=1, seed=0)(pair)

    np.testing.assert_array_equal(result.wsi.data, np.fliplr(source.data))
    np.testing.assert_allclose(result.wsi.pixel_to_reference.apply([[0, 0]]), [[4, 0]])
    np.testing.assert_allclose(result.registration.matrix, Transform.identity().matrix, atol=1e-12)


def test_random_flip_probability_zero_returns_original_sample():
    image = np.arange(6).reshape(2, 3)

    assert T.RandomHorizontalFlip(p=0, seed=0)(image) is image
    assert T.RandomVerticalFlip(p=0, seed=0)(image) is image


def test_random_rotate90_probability_zero_returns_original_sample():
    image = np.arange(6).reshape(2, 3)

    assert T.RandomRotate90(p=0, seed=0)(image) is image


def test_random_vertical_flip_reindexes_point_image():
    image = DImage(
        values=np.array([10, 20]),
        coordinates=np.array([[0, 0], [1, 2]]),
    )

    result = T.RandomVerticalFlip(p=1, seed=0)(image)

    np.testing.assert_array_equal(result.coordinates, [[0, 2], [1, 0]])
    np.testing.assert_array_equal(result.values, image.values)


def test_random_horizontal_flip_reindexes_sparse_image():
    image = SImage(
        values=sparse.csr_matrix([[1, 0], [0, 2]]),
        coordinates=np.array([[0, 0], [2, 0]]),
    )

    result = T.RandomHorizontalFlip(p=1, seed=0)(image)

    np.testing.assert_array_equal(result.coordinates, [[2, 0], [0, 0]])
    np.testing.assert_array_equal(result.values.toarray(), image.values.toarray())


def test_pair_geometry_materializes_raw_msi_before_reindexing(monkeypatch):
    class FakeMSI:
        metadata = SimpleNamespace(
            width=2,
            height=1,
            mpp=SimpleNamespace(x=1.0, y=1.0),
        )
        coordinates = np.array([[0, 0], [1, 0]])

    class FakeToRImage:
        def __call__(self, image):
            assert isinstance(image, FakeMSI)
            return RImage(
                coordinates=image.coordinates,
                positions=np.array([100.0, 200.0]),
                values=np.array([1.0, 2.0]),
                offsets=np.array([0, 1, 2]),
            )

    monkeypatch.setattr(geometry_module, 'MSI', FakeMSI)
    monkeypatch.setattr(spatial_module, 'MSI', FakeMSI)
    monkeypatch.setattr(msi_module, 'ToRImage', FakeToRImage)
    pair = PairedImage(
        spatial(np.array([[3, 4]])),
        FakeMSI(),
        Transform.identity(),
    )

    result = T.RandomHorizontalFlip(p=1, seed=0)(pair)

    assert isinstance(result.msi.data, RImage)
    np.testing.assert_array_equal(result.msi.data.coordinates, [[1, 0], [0, 0]])
    np.testing.assert_allclose(result.registration.matrix, Transform.identity().matrix)


def test_random_rotate90_rotates_non_square_array_and_frame():
    source = spatial(np.array([[1, 2, 3], [4, 5, 6]]))

    result = T.RandomRotate90(p=1, choices=(1,), seed=0)(source)

    np.testing.assert_array_equal(result.data, np.rot90(source.data))
    assert (result.geometry.width, result.geometry.height) == (2, 3)
    np.testing.assert_allclose(result.pixel_to_reference.apply([[0, 0]]), [[2, 0]])


@pytest.mark.parametrize(('turns', 'expected'), [
    (0, np.array([[1, 2], [3, 4]])),
    (2, np.array([[4, 3], [2, 1]])),
    (3, np.array([[3, 1], [4, 2]])),
])
def test_random_rotate90_supports_all_turn_counts(turns, expected):
    result = T.RandomRotate90(p=1, choices=(turns,), seed=0)(np.array([[1, 2], [3, 4]]))

    np.testing.assert_array_equal(result, expected)


def test_center_crop_uses_center_of_single_image():
    image = np.arange(36).reshape(6, 6)

    result = T.CenterCrop((2, 2))(image)

    np.testing.assert_array_equal(result, image[2:4, 2:4])


def test_center_crop_handles_exact_fit_and_line_of_valid_origins():
    exact = np.arange(20).reshape(4, 5)
    line = np.arange(50).reshape(5, 10)

    np.testing.assert_array_equal(T.CenterCrop((4, 5))(exact), exact)
    np.testing.assert_array_equal(T.CenterCrop((5, 4))(line), line[:, 3:7])


def test_center_crop_uses_registered_pair_overlap():
    values = np.arange(36).reshape(6, 6)
    pair = PairedImage(spatial(values), spatial(values * 2), Transform.identity())

    result = T.CenterCrop((2, 2))(pair)

    np.testing.assert_array_equal(result.msi.data, result.wsi.data * 2)
    np.testing.assert_allclose(result.registration.matrix, Transform.identity().matrix)


def test_pad_fills_array_and_moves_spatial_origin():
    source = spatial(np.array([[1, 2], [3, 4]]), mpp=2)

    result = T.Pad((1, 2, 3, 0), fill=9)(source)

    np.testing.assert_array_equal(result.data, np.pad(source.data, ((2, 0), (1, 3)), constant_values=9))
    assert (result.geometry.width, result.geometry.height) == (6, 4)
    np.testing.assert_allclose(result.pixel_to_reference.apply([[1, 2]]), [[0, 0]])


def test_pad_accepts_scalar_padding_and_per_channel_fill():
    image = np.ones((2, 2, 3), dtype=np.uint8)

    result = T.Pad(1, fill=(10, 20, 30))(image)
    scalar_fill = T.Pad(1, fill=7)(image)

    assert result.shape == (4, 4, 3)
    np.testing.assert_array_equal(result[0, 0], [10, 20, 30])
    np.testing.assert_array_equal(result[1:3, 1:3], image)
    np.testing.assert_array_equal(scalar_fill[0, 0], [7, 7, 7])


def test_pad_rejects_fill_with_wrong_channel_count():
    with pytest.raises(ValueError, match='3 channel values'):
        T.Pad(1, fill=(1, 2))(np.ones((2, 2, 3)))


def test_pad_reindexes_ragged_coordinates_without_changing_spectra():
    image = RImage(
        coordinates=np.array([[0, 0], [1, 1]]),
        positions=np.array([100.0, 200.0]),
        values=np.array([1.0, 2.0]),
        offsets=np.array([0, 1, 2]),
    )

    result = T.Pad((2, 1))(image)

    np.testing.assert_array_equal(result.coordinates, [[2, 1], [3, 2]])
    np.testing.assert_array_equal(result.positions, image.positions)
    np.testing.assert_array_equal(result.values, image.values)


def test_resize_nearest_repeats_pixels_and_updates_resolution():
    source = spatial(np.array([[1, 2], [3, 4]]), mpp=2)

    result = T.Resize((4, 4), interpolation='nearest')(source)

    np.testing.assert_array_equal(result.data, np.repeat(np.repeat(source.data, 2, axis=0), 2, axis=1))
    np.testing.assert_allclose(result.geometry.mpp, [1, 1])
    np.testing.assert_allclose(result.pixel_to_reference.matrix, Transform.scale(1).matrix)


def test_resize_reindexes_dense_point_coordinates():
    image = DImage(
        values=np.array([1, 2]),
        coordinates=np.array([[0, 0], [1, 1]]),
    )

    result = T.Resize((4, 4))(image)

    np.testing.assert_array_equal(result.coordinates, [[0, 0], [2, 2]])


def test_resize_reads_raw_wsi_at_target_resolution(monkeypatch):
    class FakeWSI:
        def __init__(self):
            self.metadata = SimpleNamespace(
                width=8,
                height=4,
                mpp=SimpleNamespace(x=2.0, y=4.0),
            )
            self.calls = []

        def read_region(self, location, shape, target_mpp):
            self.calls.append((location, shape, target_mpp))
            return np.ones((*shape, 3), dtype=np.uint8)

    monkeypatch.setattr(geometry_module, 'WSI', FakeWSI)
    monkeypatch.setattr(spatial_module, 'WSI', FakeWSI)
    image = FakeWSI()

    result = T.Resize((2, 4))(image)

    assert result.shape == (2, 4, 3)
    assert image.calls == [((0, 0), (2, 4), (4.0, 8.0))]


def test_resample_preserves_field_of_view_at_requested_mpp():
    source = spatial(np.arange(16).reshape(4, 4), mpp=2)

    result = T.Resample(mpp=1, interpolation='nearest')(source)

    assert result.data.shape == (8, 8)
    np.testing.assert_allclose(result.geometry.mpp, [1, 1])


def test_resample_pair_retains_registration():
    source = spatial(np.arange(16).reshape(4, 4), mpp=2)

    result = T.Resample(1, interpolation='nearest')(
        PairedImage(source, source, Transform.identity())
    )

    np.testing.assert_array_equal(result.wsi.data, result.msi.data)
    np.testing.assert_allclose(result.registration.matrix, Transform.identity().matrix)


def test_geometric_transform_rejects_unsupported_spatial_payload():
    image = SpatialImage(
        object(),
        Geometry(width=2, height=2, mpp=1),
        Transform.identity(),
    )

    with pytest.raises(TypeError, match='do not support object'):
        T.Pad(1)(image)


def test_random_resized_crop_returns_fixed_aligned_pair_shape():
    values = np.arange(100, dtype=np.float64).reshape(10, 10)
    pair = PairedImage(spatial(values), spatial(values * 2), Transform.identity())

    result = T.RandomResizedCrop(
        (4, 5),
        scale=(0.25, 0.25),
        ratio=(1, 1),
        seed=4,
    )(pair)

    assert result.wsi.data.shape == (4, 5)
    assert result.msi.data.shape == (4, 5)
    np.testing.assert_allclose(result.msi.data, result.wsi.data * 2)
    np.testing.assert_allclose(result.registration.matrix, Transform.identity().matrix)


def test_random_resized_crop_supports_single_image():
    image = np.arange(100, dtype=np.float64).reshape(10, 10)

    result = T.RandomResizedCrop(4, scale=(0.25, 0.25), ratio=(1, 1), seed=4)(image)

    assert result.shape == (4, 4)


def test_random_resized_crop_falls_back_for_impossible_sampled_aspect():
    image = np.arange(20, dtype=np.float64).reshape(2, 10)

    result = T.RandomResizedCrop(2, scale=(1, 1), ratio=(1, 1), seed=4)(image)

    assert result.shape == (2, 2)


def test_random_resized_crop_retries_failed_candidate(monkeypatch):
    original = geometry_module.RandomCrop

    class RejectingCrop:
        _bounds = staticmethod(original._bounds)

        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, image):
            raise ValueError('candidate is numerically outside the image')

    monkeypatch.setattr(geometry_module, 'RandomCrop', RejectingCrop)

    result = T.RandomResizedCrop(2, scale=(0.25, 0.25), ratio=(1, 1), seed=4)(
        np.arange(64).reshape(8, 8)
    )

    assert result.shape == (2, 2)


def test_random_resized_crop_rejects_unregistered_pair():
    pair = PairedImage(spatial(np.ones((4, 4))), spatial(np.ones((4, 4))))

    with pytest.raises(ValueError, match='registered pair'):
        T.RandomResizedCrop(2)(pair)


def test_random_affine_shares_transform_across_aligned_pair():
    values = np.arange(25, dtype=np.float64).reshape(5, 5)
    pair = PairedImage(spatial(values), spatial(values * 2), Transform.identity())

    result = T.RandomAffine(
        degrees=(-25, 25),
        translate=(0.1, 0.1),
        scale=(0.9, 1.1),
        shear=(-5, 5),
        interpolation='bilinear',
        seed=12,
    )(pair)

    np.testing.assert_allclose(result.msi.data, result.wsi.data * 2)
    np.testing.assert_allclose(result.registration.matrix, Transform.identity().matrix, atol=1e-12)


def test_random_affine_rejects_unbounded_raw_wsi(monkeypatch):
    class FakeWSI:
        metadata = SimpleNamespace(
            width=4,
            height=4,
            mpp=SimpleNamespace(x=1.0, y=1.0),
        )

    monkeypatch.setattr(geometry_module, 'WSI', FakeWSI)
    monkeypatch.setattr(spatial_module, 'WSI', FakeWSI)

    with pytest.raises(TypeError, match='in-memory crop'):
        T.RandomAffine(10)(FakeWSI())


def test_random_affine_accepts_scalar_and_four_axis_shear():
    image = np.arange(25, dtype=np.float64).reshape(5, 5)

    scalar = T.RandomAffine(0, shear=5, seed=1)(image)
    four_axis = T.RandomAffine(0, shear=(-5, 5, -2, 2), seed=1)(image)

    assert scalar.shape == image.shape
    assert four_axis.shape == image.shape


@pytest.mark.parametrize('constructor', [
    lambda: T.RandomHorizontalFlip(p=2),
    lambda: T.RandomVerticalFlip(p=-1),
    lambda: T.RandomRotate90(p=2),
    lambda: T.RandomRotate90(choices=()),
    lambda: T.Pad((-1, 0)),
    lambda: T.Pad((1, 2, 3)),
    lambda: T.Resize((0, 2)),
    lambda: T.Resize(2, interpolation='area'),
    lambda: T.Resample(0),
    lambda: T.Resample(1, interpolation='area'),
    lambda: T.RandomResizedCrop(2, scale=(1, 0.5)),
    lambda: T.RandomResizedCrop(2, scale=(0.5, 1.1)),
    lambda: T.RandomResizedCrop(2, ratio=(1, 0.5)),
    lambda: T.RandomAffine(10, translate=(2, 0)),
    lambda: T.RandomAffine((1, 2, 3)),
    lambda: T.RandomAffine(10, scale=(2, 1)),
    lambda: T.RandomAffine(10, shear=(1, 2, 3)),
    lambda: T.RandomAffine(10, interpolation='area'),
])
def test_geometry_transforms_validate_parameters(constructor):
    with pytest.raises(ValueError):
        constructor()
