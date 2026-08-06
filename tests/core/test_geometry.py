import numpy as np

from imzdesk.core import Geometry, Transform


def test_geometry_expands_scalar_mpp():
    geometry = Geometry(width=10, height=20, mpp=0.5)

    assert geometry.width == 10
    assert geometry.height == 20
    np.testing.assert_allclose(geometry.mpp, [0.5, 0.5])


def test_geometry_keeps_axis_wise_mpp():
    geometry = Geometry(width=10, height=20, mpp=(0.25, 0.5), origin=(3, 4))

    np.testing.assert_allclose(geometry.mpp, [0.25, 0.5])
    np.testing.assert_allclose(geometry.origin, [3, 4])


def test_transform_translation_apply_and_inverse():
    transform = Transform.translation(3, -2)
    points = np.array([[0, 0], [1, 5]], dtype=np.float64)

    transformed = transform.apply(points)

    np.testing.assert_allclose(transformed, [[3, -2], [4, 3]])
    np.testing.assert_allclose(transform.inverse().apply(transformed), points)


def test_transform_composition_order():
    transform = Transform.translation(10, 0) @ Transform.scale(2)

    np.testing.assert_allclose(transform.apply([[1, 1]]), [[12, 2]])


def test_transform_supports_axis_wise_scaling():
    transform = Transform.scale((2, 3))

    np.testing.assert_allclose(transform.apply([[1, 1]]), [[2, 3]])


def test_transform_rotation_around_center():
    transform = Transform.rotation(np.pi / 2, center=(1, 1))

    np.testing.assert_allclose(transform.apply([[2, 1]]), [[1, 2]], atol=1e-12)
