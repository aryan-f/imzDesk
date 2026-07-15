import pytest

from imzdesk.core.metadata import BoundingBox, Dimensions, Metadata


def test_metadata_size_uses_axis_wise_mpp_in_centimeters():
    metadata = Metadata(
        width=20_000,
        height=10_000,
        mpp=Dimensions(x=0.5, y=1.0),
    )

    assert metadata.size == Dimensions(x=1.0, y=1.0)


def test_metadata_size_is_none_without_resolution():
    metadata = Metadata(width=100, height=100)

    assert metadata.size is None


def test_bounding_box_allows_full_width_and_height():
    box = BoundingBox(x=0, y=0, width=1, height=1)

    assert box.width == 1
    assert box.height == 1


def test_bounding_box_rejects_origin_outside_unit_interval():
    with pytest.raises(ValueError):
        BoundingBox(x=1, y=0, width=0.5, height=0.5)


def test_metadata_from_empty_yaml_file(tmp_path):
    path = tmp_path / 'empty.yaml'
    path.write_text('', encoding='utf-8')

    metadata = Metadata.from_file(path)

    assert metadata == Metadata()
