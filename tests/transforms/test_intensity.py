import builtins

import numpy as np
import pytest

import imzdesk.transforms as T
from imzdesk.core import Geometry, PairedImage, SpatialImage, Transform


def spatial(values):
    height, width = values.shape[:2]
    return SpatialImage(
        values,
        Geometry(width=width, height=height, mpp=1),
        Transform.identity(),
    )


def test_gaussian_blur_smooths_numpy_impulse_without_changing_shape():
    image = np.zeros((7, 7), dtype=np.float32)
    image[3, 3] = 1

    result = T.GaussianBlur(3, sigma=1, seed=0)(image)

    assert result.shape == image.shape
    assert 0 < result[3, 3] < 1
    assert result[3, 3] > result[3, 2] > 0


def test_gaussian_blur_preserves_integer_rgb_dtype():
    image = np.zeros((5, 5, 3), dtype=np.uint8)
    image[2, 2] = [255, 128, 64]

    result = T.GaussianBlur((3, 5), sigma=(1, 1), seed=0)(image)

    assert result.shape == image.shape
    assert result.dtype == np.uint8
    assert np.all(result[2, 2] > 0)


def test_gaussian_blur_applies_same_sigma_to_pair_and_preserves_registration():
    image = np.zeros((7, 7), dtype=np.float32)
    image[3, 3] = 1
    pair = PairedImage(spatial(image), spatial(image * 2), Transform.identity())

    result = T.GaussianBlur(3, sigma=(0.5, 2), seed=4)(pair)

    np.testing.assert_allclose(result.msi.data, result.wsi.data * 2)
    assert result.registration is pair.registration


def test_gaussian_blur_supports_channel_first_tensor():
    torch = pytest.importorskip('torch')
    image = torch.zeros((2, 5, 5), dtype=torch.float32)
    image[:, 2, 2] = torch.tensor([1.0, 2.0])

    result = T.GaussianBlur(3, sigma=1)(image)

    assert result.shape == image.shape
    torch.testing.assert_close(result[1], result[0] * 2)


def test_gaussian_blur_rejects_batched_tensor():
    torch = pytest.importorskip('torch')

    with pytest.raises(TypeError, match='2D or channel-first 3D'):
        T.GaussianBlur(3)(torch.zeros((1, 2, 5, 5)))


def test_color_jitter_applies_fixed_brightness_to_rgb():
    image = np.full((2, 2, 3), 20, dtype=np.uint8)

    result = T.ColorJitter(brightness=(2, 2), seed=0)(image)

    np.testing.assert_array_equal(result, np.full_like(image, 40))


def test_color_jitter_supports_saturation_and_hue():
    image = np.zeros((2, 2, 3), dtype=np.float32)
    image[..., 0] = 1

    grayscale = T.ColorJitter(saturation=(0, 0), seed=0)(image)
    shifted = T.ColorJitter(hue=(0.5, 0.5), seed=0)(image)

    np.testing.assert_allclose(grayscale[..., 0], grayscale[..., 1])
    np.testing.assert_allclose(grayscale[..., 1], grayscale[..., 2])
    np.testing.assert_allclose(
        shifted,
        np.broadcast_to(np.array([0, 1, 1], dtype=np.float32), image.shape),
        atol=1e-6,
    )


def test_color_jitter_changes_only_wsi_member_of_pair():
    wsi = spatial(np.full((2, 2, 3), 20, dtype=np.uint8))
    msi = spatial(np.ones((2, 2), dtype=np.float32))
    pair = PairedImage(wsi, msi, Transform.identity())

    result = T.ColorJitter(brightness=(2, 2), seed=0)(pair)

    np.testing.assert_array_equal(result.wsi.data, np.full((2, 2, 3), 40))
    assert result.msi is msi
    assert result.registration is pair.registration


def test_random_erasing_shares_normalized_region_across_pair():
    pair = PairedImage(
        np.ones((4, 4), dtype=np.float32),
        np.ones((4, 4), dtype=np.float32) * 2,
        Transform.identity(),
    )

    result = T.RandomErasing(
        p=1,
        scale=(0.25, 0.25),
        ratio=(1, 1),
        value=0,
        seed=7,
    )(pair)

    assert np.count_nonzero(result.wsi == 0) == 4
    np.testing.assert_array_equal(result.wsi == 0, result.msi == 0)
    assert result.registration is pair.registration


def test_random_erasing_probability_zero_returns_original():
    image = np.ones((4, 4))

    assert T.RandomErasing(p=0, seed=0)(image) is image


def test_random_erasing_supports_channel_first_tensor():
    torch = pytest.importorskip('torch')
    image = torch.ones((3, 4, 4))

    result = T.RandomErasing(
        p=1,
        scale=(0.25, 0.25),
        ratio=(1, 1),
        value=2,
        seed=3,
    )(image)

    assert torch.count_nonzero(result == 2) == 12
    assert torch.count_nonzero(image == 2) == 0


def test_random_erasing_supports_per_channel_values():
    image = np.zeros((2, 2, 3), dtype=np.uint8)

    result = T.RandomErasing(
        p=1,
        scale=(1, 1),
        ratio=(1, 1),
        value=(10, 20, 30),
        seed=3,
    )(image)

    np.testing.assert_array_equal(result, np.broadcast_to([10, 20, 30], image.shape))


def test_random_erasing_supports_sequence_values_for_tensors_and_2d_images():
    torch = pytest.importorskip('torch')
    tensor = torch.zeros((3, 2, 2), dtype=torch.uint8)
    image = np.zeros((2, 2), dtype=np.uint8)

    tensor_result = T.RandomErasing(
        p=1,
        scale=(1, 1),
        ratio=(1, 1),
        value=(10, 20, 30),
        seed=3,
    )(tensor)
    image_result = T.RandomErasing(
        p=1,
        scale=(1, 1),
        ratio=(1, 1),
        value=(7,),
        seed=3,
    )(image)

    torch.testing.assert_close(
        tensor_result,
        torch.tensor([10, 20, 30], dtype=torch.uint8)[:, None, None].expand_as(tensor),
    )
    np.testing.assert_array_equal(image_result, np.full_like(image, 7))


def test_random_erasing_rejects_wrong_number_of_values():
    with pytest.raises(ValueError, match='one or 3 erase values'):
        T.RandomErasing(p=1, value=(1, 2))(np.zeros((2, 2, 3)))


def test_random_erasing_rejects_batched_tensor():
    torch = pytest.importorskip('torch')

    with pytest.raises(TypeError, match='2D or channel-first 3D'):
        T.RandomErasing(p=1)(torch.ones((1, 3, 4, 4)))


def test_channel_normalize_numpy_rgb():
    image = np.array([[[1.0, 2.0, 5.0]]], dtype=np.float32)

    result = T.ChannelNormalize(mean=[1, 0, 1], std=[2, 2, 4])(image)

    np.testing.assert_allclose(result, [[[0, 1, 1]]])
    assert result.dtype == np.float32


def test_channel_normalize_scalar_applies_to_both_pair_members():
    pair = PairedImage(
        np.array([[1.0, 3.0]]),
        np.array([[5.0, 7.0]]),
        Transform.identity(),
    )

    result = T.ChannelNormalize(mean=1, std=2)(pair)

    np.testing.assert_allclose(result.wsi, [[0, 1]])
    np.testing.assert_allclose(result.msi, [[2, 3]])


def test_channel_normalize_channel_first_tensor():
    torch = pytest.importorskip('torch')
    image = torch.tensor([[[1.0]], [[3.0]]])

    result = T.ChannelNormalize(mean=[1, 1], std=[1, 2])(image)

    torch.testing.assert_close(result, torch.tensor([[[0.0]], [[1.0]]]))


def test_channel_normalize_integer_2d_tensor_returns_float():
    torch = pytest.importorskip('torch')
    image = torch.tensor([[1, 3]], dtype=torch.uint8)

    result = T.ChannelNormalize(mean=1, std=2)(image)

    assert result.dtype == torch.float32
    torch.testing.assert_close(result, torch.tensor([[0.0, 1.0]]))


@pytest.mark.parametrize('image, mean, message', [
    (lambda torch: torch.zeros((1, 2, 3, 4)), 0, '2D or channel-first 3D'),
    (lambda torch: torch.zeros((2, 3, 4)), [0, 0, 0], 'Expected one or 2'),
    (lambda torch: torch.zeros((3, 4)), [0, 0], 'Expected one'),
])
def test_channel_normalize_rejects_invalid_tensor_channels(image, mean, message):
    torch = pytest.importorskip('torch')

    with pytest.raises((TypeError, ValueError), match=message):
        T.ChannelNormalize(mean=mean, std=np.ones(np.size(mean)))(image(torch))


def test_channel_normalize_rejects_invalid_numpy_channels():
    with pytest.raises(ValueError, match='Expected one or 2'):
        T.ChannelNormalize(mean=[0, 0, 0], std=[1, 1, 1])(np.zeros((2, 2, 2)))


def test_numpy_transforms_work_when_torch_is_unavailable(monkeypatch):
    original_import = builtins.__import__

    def reject_torch(name, *args, **kwargs):
        if name == 'torch':
            raise ImportError
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', reject_torch)

    result = T.ChannelNormalize(0, 1)(np.ones((2, 2)))

    np.testing.assert_array_equal(result, np.ones((2, 2)))


@pytest.mark.parametrize('constructor', [
    lambda: T.GaussianBlur(2),
    lambda: T.GaussianBlur(3, sigma=0),
    lambda: T.GaussianBlur(3, sigma=(1, 2, 3)),
    lambda: T.GaussianBlur(3, sigma=(-1, 1)),
    lambda: T.ColorJitter(brightness=-1),
    lambda: T.ColorJitter(brightness=(-1, 1)),
    lambda: T.ColorJitter(hue=0.6),
    lambda: T.RandomErasing(p=2),
    lambda: T.RandomErasing(scale=(0.5, 1.5)),
    lambda: T.RandomErasing(ratio=(1, 0.5)),
    lambda: T.ChannelNormalize(mean=[0, 1], std=[1]),
    lambda: T.ChannelNormalize(mean=0, std=0),
])
def test_intensity_transforms_validate_parameters(constructor):
    with pytest.raises(ValueError):
        constructor()


@pytest.mark.parametrize('transform', [
    T.GaussianBlur(3),
    T.ColorJitter(),
    T.RandomErasing(p=1),
    T.ChannelNormalize(0, 1),
])
def test_intensity_transforms_reject_non_raster_input(transform):
    with pytest.raises(TypeError):
        transform(object())
