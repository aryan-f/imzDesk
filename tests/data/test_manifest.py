import yaml

from imzdesk.data import DatasetManifest


def test_manifest_lists_missing_workspace_directory(tmp_path):
    manifests = DatasetManifest.list_workspace(tmp_path)

    assert manifests == []
    assert DatasetManifest.directory(tmp_path).is_dir()


def test_manifest_round_trips_single_dataset_file(tmp_path):
    manifest = DatasetManifest(
        id='paired',
        name='Paired',
        kind='paired',
        splits={
            'train': [
                {
                    'id': 'sample',
                    'wsi': 'sample.ndpi',
                    'msi': 'sample.imzML',
                },
            ],
        },
    )

    manifest.to_workspace(tmp_path)
    loaded = DatasetManifest.from_workspace(tmp_path, 'paired')

    assert loaded == manifest
    with open(DatasetManifest.path(tmp_path, 'paired'), 'r', encoding='utf-8') as f:
        assert yaml.safe_load(f) == manifest.model_dump()


def test_manifest_directory_uses_workspace_sidecar(tmp_path):
    assert DatasetManifest.directory(tmp_path) == tmp_path / '.imzDesk' / 'datasets'
    assert DatasetManifest.path(tmp_path, 'a') == tmp_path / '.imzDesk' / 'datasets' / 'a.yaml'


def test_manifest_lists_independent_dataset_files(tmp_path):
    DatasetManifest(id='a', name='A', kind='wsi', splits={}).to_workspace(tmp_path)
    DatasetManifest(id='b', name='B', kind='msi', splits={}).to_workspace(tmp_path)

    manifests = DatasetManifest.list_workspace(tmp_path)

    assert [manifest.id for manifest in manifests] == ['a', 'b']


def test_manifest_deletes_single_dataset_file(tmp_path):
    DatasetManifest(id='a', name='A', kind='wsi', splits={}).to_workspace(tmp_path)
    DatasetManifest(id='b', name='B', kind='msi', splits={}).to_workspace(tmp_path)

    DatasetManifest.delete_workspace(tmp_path, 'b')

    assert DatasetManifest.path(tmp_path, 'a').exists()
    assert not DatasetManifest.path(tmp_path, 'b').exists()
