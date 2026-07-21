from imzdesk.core.metadata import Dimensions, Metadata
from imzdesk.io.base import ImageBase


class FakeImage(ImageBase):
    metadata_class = Metadata
    extensions = ('.fake',)

    @classmethod
    def init_metadata(cls, filepath):
        return Metadata(width=10, height=20, mpp=Dimensions(x=0.5, y=1.0))


def test_derived_path_for_places_sidecar_under_imzdesk_directory(tmp_path):
    filepath = tmp_path / 'sample.fake'

    derived = FakeImage.derived_path_for(filepath, '.meta.yaml')

    assert derived == tmp_path / '.imzDesk' / 'sample.meta.yaml'


def test_read_metadata_initializes_missing_sidecar(tmp_path):
    filepath = tmp_path / 'sample.fake'
    filepath.write_text('fake', encoding='utf-8')

    metadata = FakeImage.read_metadata(filepath)

    assert metadata.width == 10
    assert metadata.height == 20
    assert FakeImage.derived_path_for(filepath, '.meta.yaml').exists()


def test_write_metadata_round_trips(tmp_path):
    filepath = tmp_path / 'sample.fake'
    metadata = Metadata(width=5, height=6, mpp=Dimensions(x=2, y=3))

    FakeImage.write_metadata(filepath, metadata)
    loaded = FakeImage.read_metadata(filepath)

    assert loaded == metadata


def test_tags_default_to_empty_list(tmp_path):
    filepath = tmp_path / 'sample.fake'

    assert FakeImage.read_tags(filepath) == []


def test_tags_empty_yaml_file_returns_empty_list(tmp_path):
    filepath = tmp_path / 'sample.fake'
    tags_path = FakeImage.derived_path_for(filepath, '.tags.yaml')
    tags_path.parent.mkdir(parents=True)
    tags_path.write_text('', encoding='utf-8')

    assert FakeImage.read_tags(filepath) == []


def test_write_tags_round_trips(tmp_path):
    filepath = tmp_path / 'sample.fake'

    tags = FakeImage.write_tags(filepath, ['organ.colon', 'stain.he'])

    assert tags == ['organ.colon', 'stain.he']
    assert FakeImage.read_tags(filepath) == ['organ.colon', 'stain.he']


def test_annotations_default_to_empty_list(tmp_path):
    filepath = tmp_path / 'sample.fake'

    assert FakeImage.read_annotations(filepath) == []


def test_annotations_empty_yaml_file_returns_empty_list(tmp_path):
    filepath = tmp_path / 'sample.fake'
    annotations_path = FakeImage.derived_path_for(filepath, '.annotations.yaml')
    annotations_path.parent.mkdir(parents=True)
    annotations_path.write_text('', encoding='utf-8')

    assert FakeImage.read_annotations(filepath) == []


def test_write_annotations_round_trips_list(tmp_path):
    filepath = tmp_path / 'sample.fake'
    annotations = [{
        'id': 'region-1',
        'label': 'region',
        'kind': 'polygon',
        'notes': '',
        'export': True,
        'project': True,
        'coordinates': [[1.0, 2.0], [3.0, 4.0]],
    }]

    written = FakeImage.write_annotations(filepath, annotations)

    assert written == annotations
    assert FakeImage.read_annotations(filepath) == annotations


def test_read_annotations_accepts_wrapped_legacy_mapping(tmp_path):
    filepath = tmp_path / 'sample.fake'
    annotations_path = FakeImage.derived_path_for(filepath, '.annotations.yaml')
    annotations_path.parent.mkdir(parents=True)
    annotations_path.write_text(
        'annotations:\n'
        '  - id: region-1\n'
        '    kind: box\n',
        encoding='utf-8',
    )

    assert FakeImage.read_annotations(filepath) == [{'id': 'region-1', 'kind': 'box'}]


def test_instance_flush_methods_write_current_state(tmp_path):
    filepath = tmp_path / 'sample.fake'
    image = FakeImage(filepath)
    image.metadata.optional['case'] = 'A'
    image.tags.append('organ.kidney')
    image.annotations.append({
        'id': 'region-1',
        'label': 'region',
        'kind': 'box',
        'notes': '',
        'export': True,
        'project': True,
        'coordinates': [[1.0, 2.0], [3.0, 4.0]],
    })

    image.flush_metadata()
    image.flush_tags()
    image.flush_annotations()

    assert FakeImage.read_metadata(filepath).optional == {'case': 'A'}
    assert FakeImage.read_tags(filepath) == ['organ.kidney']
    assert FakeImage.read_annotations(filepath)[0]['id'] == 'region-1'


def test_instance_path_properties_and_setters(tmp_path):
    filepath = tmp_path / 'sample.fake'
    image = FakeImage(filepath)
    metadata = Metadata(width=1, height=1, mpp=Dimensions(x=1, y=1))

    image.metadata = metadata
    image.tags = ['manual']
    image.annotations = [{'id': 'manual'}]

    assert image.metadata is metadata
    assert image.tags == ['manual']
    assert image.annotations == [{'id': 'manual'}]
    assert image.metadata_path == tmp_path / '.imzDesk' / 'sample.meta.yaml'
    assert image.tags_path == tmp_path / '.imzDesk' / 'sample.tags.yaml'
    assert image.annotations_path == tmp_path / '.imzDesk' / 'sample.annotations.yaml'
