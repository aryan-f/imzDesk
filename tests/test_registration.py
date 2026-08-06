from types import SimpleNamespace

import numpy as np

import imzdesk.registration as registration_module
from imzdesk.core import Transform
from imzdesk.core.metadata import BoundingBox, Dimensions
from imzdesk.registration import (
    apply_wsi_crop_offset,
    centroid,
    centroid_initialization,
    chamfer_loss,
    contour,
    iou,
    ncc,
    rotation_sweep,
    warp,
)


def test_centroid_uses_values_as_weights():
    image = np.array([
        [0.0, 1.0],
        [0.0, 3.0],
    ])

    np.testing.assert_allclose(centroid(image), [1.0, 0.75])


def test_centroid_accepts_extra_weights():
    image = np.array([
        [1.0, 1.0],
        [1.0, 1.0],
    ])
    weights = np.array([
        [0.0, 0.0],
        [0.0, 4.0],
    ])

    np.testing.assert_allclose(centroid(image, weights=weights), [1.0, 1.0])


def test_centroid_of_empty_mask_returns_center():
    mask = np.zeros((3, 5), dtype=bool)

    np.testing.assert_allclose(centroid(mask), [2.0, 1.0])


def test_contour_returns_boundary_pixels():
    mask = np.zeros((5, 5), dtype=bool)
    mask[1:4, 1:4] = True

    result = contour(mask)

    expected = np.array([
        [False, False, False, False, False],
        [False, True, True, True, False],
        [False, True, False, True, False],
        [False, True, True, True, False],
        [False, False, False, False, False],
    ])
    np.testing.assert_array_equal(result, expected)


def test_warp_identity_preserves_image():
    image = np.array([
        [0.0, 1.0],
        [2.0, 3.0],
    ])

    warped = warp(image, Transform.identity(), output_shape=image.shape)

    np.testing.assert_allclose(warped, image)


def test_warp_translation_moves_image_in_fixed_space():
    image = np.array([
        [1.0, 0.0],
        [0.0, 0.0],
    ])

    warped = warp(image, Transform.translation(1, 0), output_shape=image.shape, order=0)

    np.testing.assert_allclose(warped, [[0.0, 1.0], [0.0, 0.0]])


def test_apply_wsi_crop_offset_converts_crop_local_transform_to_full_slide_coordinates():
    wsi = SimpleNamespace(
        metadata=SimpleNamespace(
            crop=BoundingBox(x=0.25, y=0.5, width=0.5, height=0.25),
            mpp=Dimensions(x=0.5, y=1.0),
        ),
        slide=SimpleNamespace(dimensions=(1000, 2000)),
    )

    transform = apply_wsi_crop_offset(wsi, target_mpp=(1.0, 2.0), transform=Transform.identity())

    np.testing.assert_allclose(transform.matrix, Transform.translation(125, 500).matrix)


def test_iou_returns_overlap_fraction_and_zero_for_empty_union():
    fixed = np.array([[True, True], [False, False]])
    moving = np.array([[True, False], [True, False]])

    assert iou(fixed, moving) == 1 / 3
    assert iou(np.zeros((2, 2), dtype=bool), np.zeros((2, 2), dtype=bool)) == 0


def test_ncc_returns_one_for_matching_masks_and_zero_for_constant_inputs():
    mask = np.array([[True, False], [False, True]])

    np.testing.assert_allclose(ncc(mask, mask), 1)
    assert ncc(np.ones((2, 2)), np.ones((2, 2))) == 0


def test_centroid_initialization_aligns_mask_centroids():
    fixed = np.zeros((5, 5), dtype=bool)
    moving = np.zeros((5, 5), dtype=bool)
    fixed[3, 3] = True
    moving[1, 1] = True

    transform = centroid_initialization(fixed, moving)

    np.testing.assert_allclose(transform.apply([[1, 1]]), [[3, 3]])


def test_chamfer_loss_is_lower_for_aligned_masks():
    fixed = np.zeros((5, 5), dtype=bool)
    moving = np.zeros((5, 5), dtype=bool)
    fixed[2, 2] = True
    moving[2, 2] = True

    aligned = chamfer_loss(fixed, moving, Transform.identity())
    shifted = chamfer_loss(fixed, moving, Transform.translation(1, 0))

    assert aligned < shifted


def test_chamfer_loss_is_infinite_without_contours():
    fixed = np.zeros((3, 3), dtype=bool)
    moving = np.zeros((3, 3), dtype=bool)

    assert np.isinf(chamfer_loss(fixed, moving, Transform.identity()))


def test_rotation_sweep_improves_orientation_for_simple_shape():
    fixed = np.zeros((9, 9), dtype=bool)
    moving = np.zeros((9, 9), dtype=bool)
    fixed[4, 2:7] = True
    moving[2:7, 4] = True

    transform = rotation_sweep(fixed, moving, Transform.identity(), angle_step=90)
    warped = warp(moving.astype(float), transform, fixed.shape, order=0) > 0.5

    assert iou(fixed, warped) == 1


def test_register_forwards_batch_size_to_embedding(monkeypatch):
    captured = {}

    class FakeEmbed:
        def __init__(self, model, batch_size):
            captured['model'] = model
            captured['batch_size'] = batch_size

    class FakeCompose:
        def __init__(self, transforms):
            self.transforms = transforms

        def __call__(self, image):
            return np.ones((2, 2), dtype=bool)

    monkeypatch.setattr(registration_module.T, 'Embed', FakeEmbed)
    monkeypatch.setattr(registration_module.T, 'Compose', FakeCompose)
    monkeypatch.setattr(
        registration_module,
        'centroid_initialization',
        lambda fixed, moving: Transform.identity(),
    )
    monkeypatch.setattr(
        registration_module,
        'rotation_sweep',
        lambda fixed, moving, transform: transform,
    )
    monkeypatch.setattr(
        registration_module,
        'chamfer_refine',
        lambda fixed, moving, transform: transform,
    )
    wsi = SimpleNamespace(metadata=SimpleNamespace(crop=None))
    msi = SimpleNamespace(
        metadata=SimpleNamespace(mpp=SimpleNamespace(x=10.0, y=20.0)),
    )

    registration_module.register(wsi, msi, batch_size=37)

    assert captured == {
        'model': 'roman-bushuiev/DreaMS',
        'batch_size': 37,
    }
