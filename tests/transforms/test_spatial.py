import builtins
from types import SimpleNamespace

import numpy as np
import pytest
from scipy import sparse

import imzdesk.transforms as T
import imzdesk.transforms.msi as msi_module
import imzdesk.transforms.spatial as spatial_module
from imzdesk.core import DImage, Geometry, PairedImage, RImage, SImage, SpatialImage, Transform


def spatial_image(values):
    height, width = values.shape[:2]
    return SpatialImage(
        data=values,
        geometry=Geometry(width=width, height=height, mpp=1),
        pixel_to_reference=Transform.identity(),
    )


def test_parallel_applies_independent_pipelines_and_updates_registration():
    registration = Transform.translation(1, 2)
    pair = PairedImage(
        wsi=spatial_image(np.ones((4, 4))),
        msi=spatial_image(np.ones((4, 4)) * 2),
        registration=registration,
    )

    result = T.Parallel(
        wsi=T.Compose([lambda image: image + 1]),
        msi=T.Compose([lambda image: image * 3]),
    )(pair)

    np.testing.assert_array_equal(result.wsi.data, np.ones((4, 4)) * 2)
    np.testing.assert_array_equal(result.msi.data, np.ones((4, 4)) * 6)
    np.testing.assert_allclose(result.registration.matrix, Transform.identity().matrix)


def test_parallel_tracks_full_frame_resize():
    pair = PairedImage(
        wsi=spatial_image(np.ones((4, 8))),
        msi=spatial_image(np.ones((4, 8))),
        registration=Transform.identity(),
    )

    result = T.Parallel(
        wsi=lambda image: image[::2, ::2],
        msi=lambda image: image,
    )(pair)

    assert (result.wsi.geometry.width, result.wsi.geometry.height) == (4, 2)
    np.testing.assert_allclose(result.wsi.pixel_to_reference.apply([[1, 1]]), [[2, 2]])
    np.testing.assert_allclose(result.registration.apply([[2, 2]]), [[1, 1]])


def test_parallel_accepts_transform_with_explicit_spatial_frame():
    source = spatial_image(np.ones((4, 4)))
    pair = PairedImage(wsi=source, msi=source, registration=Transform.identity())
    moved = SpatialImage(
        data=np.ones((2, 2)) * 7,
        geometry=Geometry(width=2, height=2, mpp=2, origin=(8, 10)),
        pixel_to_reference=Transform.translation(8, 10) @ Transform.scale(2),
    )

    result = T.Parallel(wsi=lambda _: moved)(pair)

    assert result.wsi is moved
    np.testing.assert_allclose(
        result.registration.matrix,
        moved.pixel_to_reference.inverse().matrix,
    )


def test_parallel_preserves_point_spacing_when_coordinates_expand():
    source = DImage(values=np.array([1.0]), coordinates=np.array([[0, 0]]))
    spatial = SpatialImage(
        data=source,
        geometry=Geometry(width=2, height=2, mpp=(3, 4), origin=(5, 6)),
        pixel_to_reference=Transform.translation(5, 6) @ Transform.scale((3, 4)),
    )
    expanded = DImage(
        values=np.array([1.0, 2.0]),
        coordinates=np.array([[0, 0], [3, 2]]),
    )

    result = T.Parallel(wsi=lambda _: expanded)(
        PairedImage(spatial, spatial, Transform.identity())
    )

    assert (result.wsi.geometry.width, result.wsi.geometry.height) == (4, 3)
    np.testing.assert_allclose(result.wsi.geometry.mpp, [3, 4])
    np.testing.assert_allclose(result.wsi.geometry.origin, [5, 6])
    np.testing.assert_allclose(result.wsi.pixel_to_reference.matrix, spatial.pixel_to_reference.matrix)


def test_parallel_rejects_nonpaired_input():
    with pytest.raises(TypeError, match='PairedImage'):
        T.Parallel()(np.ones((2, 2)))


def test_parallel_builds_spatial_frames_for_raw_pair(monkeypatch):
    class FakeWSI:
        metadata = SimpleNamespace(
            width=8,
            height=4,
            mpp=SimpleNamespace(x=2.0, y=2.0),
            crop=None,
        )

    class FakeMSI:
        metadata = SimpleNamespace(
            width=4,
            height=2,
            mpp=SimpleNamespace(x=2.0, y=2.0),
        )
        coordinates = np.array([[1, 1], [4, 2]])

    monkeypatch.setattr(spatial_module, 'WSI', FakeWSI)
    monkeypatch.setattr(spatial_module, 'MSI', FakeMSI)
    registration = Transform.translation(3, 4)

    result = T.Parallel()(PairedImage(FakeWSI(), FakeMSI(), registration))

    assert isinstance(result.wsi, SpatialImage)
    assert isinstance(result.msi, SpatialImage)
    assert (result.msi.geometry.width, result.msi.geometry.height) == (5, 3)
    np.testing.assert_allclose(result.registration.matrix, registration.matrix)


def test_native_msi_frame_falls_back_to_metadata_for_empty_coordinates(monkeypatch):
    class FakeMSI:
        metadata = SimpleNamespace(
            width=7,
            height=5,
            mpp=SimpleNamespace(x=2.0, y=3.0),
        )
        coordinates = np.empty((0, 3))

    monkeypatch.setattr(spatial_module, 'MSI', FakeMSI)

    result = spatial_module._native_spatial(FakeMSI())

    assert (result.geometry.width, result.geometry.height) == (7, 5)
    np.testing.assert_allclose(result.pixel_to_reference.matrix, Transform.scale((2, 3)).matrix)


def test_native_frame_rejects_missing_resolution(monkeypatch):
    class FakeWSI:
        metadata = SimpleNamespace(width=2, height=2, mpp=None)

    monkeypatch.setattr(spatial_module, 'WSI', FakeWSI)

    with pytest.raises(ValueError, match='no spatial resolution'):
        spatial_module._native_spatial(FakeWSI())


def test_parallel_rejects_wsi_crop_without_an_updated_spatial_frame(monkeypatch):
    class FakeWSI:
        metadata = SimpleNamespace(
            width=8,
            height=4,
            mpp=SimpleNamespace(x=2.0, y=2.0),
            crop=object(),
        )

    class FakeMSI:
        metadata = SimpleNamespace(
            width=4,
            height=2,
            mpp=SimpleNamespace(x=2.0, y=2.0),
        )
        coordinates = np.array([[0, 0]])

    monkeypatch.setattr(spatial_module, 'WSI', FakeWSI)
    monkeypatch.setattr(spatial_module, 'MSI', FakeMSI)
    pair = PairedImage(FakeWSI(), FakeMSI(), Transform.identity())

    with pytest.raises(ValueError, match=r'ToImage\(crop=True\)'):
        T.Parallel(wsi=T.ToImage())(pair)


def test_parallel_rasterizes_dense_image_on_declared_spatial_canvas():
    dense = DImage(
        values=np.array([1.0, 2.0]),
        coordinates=np.array([[1, 1], [2, 2]]),
    )
    spatial = SpatialImage(
        data=dense,
        geometry=Geometry(width=4, height=4, mpp=2),
        pixel_to_reference=Transform.scale(2),
    )
    pair = PairedImage(wsi=spatial, msi=spatial, registration=Transform.identity())

    result = T.Parallel(wsi=T.ToImage(), msi=T.ToImage())(pair)

    assert result.wsi.data.shape == (4, 4)
    assert result.msi.data.shape == (4, 4)
    np.testing.assert_allclose(result.msi.pixel_to_reference.matrix, Transform.scale(2).matrix)


def test_random_crop_uses_same_region_for_registered_pair():
    values = np.arange(100, dtype=np.float32).reshape(10, 10)
    pair = PairedImage(
        wsi=spatial_image(values),
        msi=spatial_image(values * 2),
        registration=Transform.identity(),
    )

    result = T.RandomCrop((4, 5), seed=4)(pair)

    assert result.wsi.data.shape == (4, 5)
    assert result.msi.data.shape == (4, 5)
    np.testing.assert_allclose(result.msi.data, result.wsi.data * 2)
    np.testing.assert_allclose(result.wsi.geometry.origin, result.msi.geometry.origin)
    np.testing.assert_allclose(result.registration.matrix, Transform.identity().matrix)


def test_random_crop_stays_inside_rotated_spatial_footprint():
    transform = Transform.rotation(np.pi / 4, center=(5, 5))
    image = SpatialImage(
        data=np.ones((10, 10), dtype=np.float32),
        geometry=Geometry(width=10, height=10, mpp=1),
        pixel_to_reference=transform,
    )
    crop = T.RandomCrop(2, seed=4)

    for _ in range(100):
        result = crop(image)
        origin = result.geometry.origin
        reference_corners = origin + np.array([[0, 0], [2, 0], [0, 2], [2, 2]])
        source_corners = transform.inverse().apply(reference_corners)
        assert np.all(source_corners >= -1e-9)
        assert np.all(source_corners <= 10 + 1e-9)


def test_random_crop_rejects_crop_that_only_fits_bounding_box():
    image = SpatialImage(
        data=np.ones((2, 10), dtype=np.float32),
        geometry=Geometry(width=10, height=2, mpp=1),
        pixel_to_reference=Transform.rotation(np.pi / 4, center=(5, 1)),
    )

    with pytest.raises(ValueError, match='does not fit'):
        T.RandomCrop(2)(image)


def test_random_crop_rejects_unregistered_pair():
    pair = PairedImage(
        wsi=spatial_image(np.ones((4, 4))),
        msi=spatial_image(np.ones((4, 4))),
    )

    with pytest.raises(ValueError, match='registered pair'):
        T.RandomCrop(2)(pair)


def test_random_crop_rejects_nonpositive_resolution():
    with pytest.raises(ValueError, match='resolution'):
        T.RandomCrop(2, mpp=0)


@pytest.mark.parametrize('size', [(0, 2), (2, -1), (1, 2, 3)])
def test_random_crop_rejects_invalid_size(size):
    with pytest.raises(ValueError, match='two positive'):
        T.RandomCrop(size)


def test_random_crop_rejects_oversized_crop_with_diagnostic_dimensions():
    with pytest.raises(ValueError, match=r'requested \(11\.0, 11\.0\).*overlap \(10\.0, 10\.0\)'):
        T.RandomCrop(11)(np.ones((10, 10)))


def test_random_crop_rejects_projective_spatial_frame():
    image = SpatialImage(
        data=np.ones((10, 10)),
        geometry=Geometry(width=10, height=10, mpp=1),
        pixel_to_reference=Transform(np.array([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.01, 0.0, 1.0],
        ])),
    )

    with pytest.raises(ValueError, match='affine'):
        T.RandomCrop(2)(image)


def test_random_crop_samples_degenerate_line_of_valid_origins():
    image = spatial_image(np.arange(50).reshape(5, 10))

    result = T.RandomCrop((5, 4), seed=12)(image)

    assert result.data.shape == (5, 4)
    assert result.geometry.origin[1] == pytest.approx(0)
    assert 0 <= result.geometry.origin[0] <= 6


def test_random_crop_uses_worker_specific_seed(monkeypatch):
    worker = SimpleNamespace(id=3, seed=987654)
    monkeypatch.setattr('torch.utils.data.get_worker_info', lambda: worker)
    crop = T.RandomCrop(2, seed=17)
    expected = np.random.default_rng(np.random.SeedSequence([17, worker.id]))

    assert crop._rng().uniform() == expected.uniform()
    assert crop._rng().uniform() == expected.uniform()


def test_random_crop_reads_shared_region_from_raw_wsi_and_msi(monkeypatch):
    class FakeWSI:
        def __init__(self):
            self.metadata = SimpleNamespace(
                width=6,
                height=6,
                mpp=SimpleNamespace(x=2.0, y=2.0),
                crop=None,
            )
            self.reads = []

        def read_region(self, location, shape, target_mpp):
            self.reads.append((location, shape, target_mpp))
            return np.full((*shape, 3), 5, dtype=np.uint8)

    class FakeMSI:
        metadata = SimpleNamespace(
            width=5,
            height=5,
            mpp=SimpleNamespace(x=2.0, y=2.0),
        )
        coordinates = np.array([[x, y] for y in range(5) for x in range(5)])

    class FakeToRImage:
        def __call__(self, image):
            count = len(image.coordinates)
            return RImage(
                coordinates=image.coordinates,
                positions=np.arange(count, dtype=np.float64),
                values=np.arange(count, dtype=np.float64),
                offsets=np.arange(count + 1),
            )

    monkeypatch.setattr(spatial_module, 'WSI', FakeWSI)
    monkeypatch.setattr(spatial_module, 'MSI', FakeMSI)
    monkeypatch.setattr(msi_module, 'ToRImage', FakeToRImage)
    wsi = FakeWSI()

    result = T.RandomCrop(2, mpp=2, seed=4)(
        PairedImage(wsi, FakeMSI(), Transform.identity())
    )

    assert result.wsi.data.shape == (2, 2, 3)
    assert isinstance(result.msi.data, RImage)
    assert len(wsi.reads) == 1
    np.testing.assert_allclose(wsi.reads[0][0] * 2, result.wsi.geometry.origin)
    assert wsi.reads[0][1:] == ((2, 2), (2.0, 2.0))
    np.testing.assert_allclose(result.wsi.geometry.origin, result.msi.geometry.origin)


def test_random_crop_supports_single_dense_array():
    image = np.arange(100).reshape(10, 10)

    result = T.RandomCrop(3, seed=2)(image)

    assert result.shape == (3, 3)


def test_random_crop_interpolates_each_rgb_channel_in_same_frame():
    base = np.arange(100, dtype=np.float64).reshape(10, 10)
    image = np.stack([base, base + 100, base * 2], axis=-1)

    result = T.RandomCrop(3, seed=2)(image)

    assert result.shape == (3, 3, 3)
    np.testing.assert_allclose(result[..., 1], result[..., 0] + 100)
    np.testing.assert_allclose(result[..., 2], result[..., 0] * 2)


def test_random_crop_preserves_ragged_spectra():
    image = RImage(
        coordinates=np.array([[0, 0], [3, 3]]),
        positions=np.array([100.0, 101.0, 200.0]),
        values=np.array([1.0, 2.0, 3.0]),
        offsets=np.array([0, 2, 3]),
    )

    result = T.RandomCrop(4, seed=0)(image)

    np.testing.assert_array_equal(result.positions, image.positions)
    np.testing.assert_array_equal(result.values, image.values)


@pytest.mark.parametrize('image_type', [SImage, DImage])
def test_random_crop_preserves_point_image_type_and_rebases_coordinates(image_type):
    values = sparse.csr_matrix([[1.0], [2.0]]) if image_type is SImage else np.array([1.0, 2.0])
    image = image_type(values=values, coordinates=np.array([[1, 1], [4, 4]]))
    spatial = SpatialImage(
        data=image,
        geometry=Geometry(width=5, height=5, mpp=1),
        pixel_to_reference=Transform.identity(),
    )

    result = T.RandomCrop(3, seed=0)(spatial)
    expected_coordinates = np.rint(image.coordinates - result.geometry.origin).astype(np.int64)
    keep = np.all((expected_coordinates >= 0) & (expected_coordinates < 3), axis=1)

    assert result.geometry.origin[0] > 0
    assert isinstance(result.data, image_type)
    np.testing.assert_array_equal(result.data.coordinates, expected_coordinates[keep])
    if image_type is SImage:
        np.testing.assert_array_equal(result.data.values.toarray(), values[keep].toarray())
    else:
        np.testing.assert_array_equal(result.data.values, values[keep])


def test_random_crop_rejects_empty_point_image():
    image = RImage(
        coordinates=np.empty((0, 2)),
        positions=np.array([]),
        values=np.array([]),
        offsets=np.array([0]),
    )

    with pytest.raises(ValueError, match='does not fit'):
        T.RandomCrop(1)(image)


def test_random_crop_does_not_require_torch(monkeypatch):
    original_import = builtins.__import__

    def reject_torch(name, *args, **kwargs):
        if name == 'torch.utils.data':
            raise ImportError('simulated missing optional dependency')
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', reject_torch)

    result = T.RandomCrop(2, seed=3)(np.ones((4, 4)))

    assert result.shape == (2, 2)


def test_random_crop_rejects_nonspatial_and_unsupported_payloads():
    with pytest.raises(ValueError, match='at least two dimensions'):
        T.RandomCrop(1)(np.array([1, 2]))
    with pytest.raises(TypeError, match='determine spatial shape'):
        T.RandomCrop(1)(object())

    wrapped = SpatialImage(
        data=object(),
        geometry=Geometry(width=2, height=2, mpp=1),
        pixel_to_reference=Transform.identity(),
    )
    with pytest.raises(TypeError, match='does not support object'):
        T.RandomCrop(1)(wrapped)


def test_to_tensor_converts_registered_pair_to_collatable_named_tuple():
    torch = pytest.importorskip('torch')
    pair = PairedImage(
        wsi=spatial_image(np.zeros((4, 5, 3), dtype=np.uint8)),
        msi=spatial_image(np.zeros((4, 5), dtype=np.float32)),
        registration=Transform.identity(),
    )

    result = T.ToTensor(dtype=torch.float32)(pair)

    assert result.wsi.shape == (3, 4, 5)
    assert result.msi.shape == (1, 4, 5)
    assert result.registration.shape == (3, 3)
    batch = next(iter(torch.utils.data.DataLoader([result, result], batch_size=2)))
    assert batch.wsi.shape == (2, 3, 4, 5)
    assert batch.msi.shape == (2, 1, 4, 5)


def test_to_tensor_uses_spatial_canvas_for_dense_image():
    torch = pytest.importorskip('torch')
    image = SpatialImage(
        data=DImage(values=np.array([2.0]), coordinates=np.array([[1, 1]])),
        geometry=Geometry(width=4, height=3, mpp=1),
        pixel_to_reference=Transform.identity(),
    )

    result = T.ToTensor()(image)

    assert result.shape == (1, 3, 4)
    assert result.dtype == torch.float64


def test_to_tensor_uses_spatial_canvas_for_sparse_image():
    torch = pytest.importorskip('torch')
    image = SpatialImage(
        data=SImage(
            values=sparse.csr_matrix([[2.0, 3.0]]),
            coordinates=np.array([[1, 1]]),
        ),
        geometry=Geometry(width=4, height=3, mpp=1),
        pixel_to_reference=Transform.identity(),
    )

    result = T.ToTensor()(image)

    assert result.shape == (2, 3, 4)
    assert result.dtype == torch.float64
    np.testing.assert_array_equal(result[:, 1, 1].numpy(), [2, 3])


def test_to_tensor_converts_all_container_forms_and_existing_tensors():
    torch = pytest.importorskip('torch')
    ragged = RImage(
        coordinates=np.array([[1, 2]]),
        positions=np.array([100.0, 101.0]),
        values=np.array([3.0, 4.0]),
        offsets=np.array([0, 2]),
    )
    sparse_image = SImage(
        values=sparse.csr_matrix([[5.0, 6.0]]),
        coordinates=np.array([[0, 0]]),
    )
    dense_image = DImage(values=np.array([[7.0, 8.0]]), coordinates=np.array([[0, 0]]))

    ragged_tensor = T.ToTensor()(ragged)
    sparse_tensor = T.ToTensor()(sparse_image)
    dense_tensor = T.ToTensor()(dense_image)
    matrix_tensor = T.ToTensor()(sparse.csr_matrix([[1.0, 2.0], [3.0, 4.0]]))
    existing = torch.tensor([1, 2])

    np.testing.assert_array_equal(ragged_tensor.coordinates.numpy(), [[1, 2]])
    np.testing.assert_array_equal(ragged_tensor.offsets.numpy(), [0, 2])
    assert sparse_tensor.shape == (2, 1, 1)
    assert dense_tensor.shape == (2, 1, 1)
    assert matrix_tensor.shape == (1, 2, 2)
    assert T.ToTensor()(existing) is existing
    assert T.ToTensor(dtype=torch.float64)(existing).dtype == torch.float64


def test_to_tensor_converts_raw_modalities(monkeypatch):
    pytest.importorskip('torch')

    class FakeWSI:
        def to_image(self):
            return np.zeros((2, 3, 3), dtype=np.uint8)

    class FakeMSI:
        coordinates = np.array([[0, 0]])

    class FakeToRImage:
        def __call__(self, image):
            return RImage(
                coordinates=image.coordinates,
                positions=np.array([100.0]),
                values=np.array([2.0]),
                offsets=np.array([0, 1]),
            )

    monkeypatch.setattr(spatial_module, 'WSI', FakeWSI)
    monkeypatch.setattr(spatial_module, 'MSI', FakeMSI)
    monkeypatch.setattr(msi_module, 'ToRImage', FakeToRImage)

    assert T.ToTensor()(FakeWSI()).shape == (3, 2, 3)
    result = T.ToTensor()(FakeMSI())
    np.testing.assert_array_equal(result.coordinates.numpy(), [[0, 0]])


def test_to_tensor_rejects_unsupported_input():
    pytest.importorskip('torch')
    with pytest.raises(TypeError, match='does not support object'):
        T.ToTensor()(object())


def test_to_tensor_explains_missing_optional_dependency(monkeypatch):
    pytest.importorskip('torch')
    original_import = builtins.__import__

    def reject_torch(name, *args, **kwargs):
        if name == 'torch':
            raise ImportError('simulated missing dependency')
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', reject_torch)

    with pytest.raises(ImportError, match='optional `torch` dependency'):
        T.ToTensor()(np.ones((2, 2)))
