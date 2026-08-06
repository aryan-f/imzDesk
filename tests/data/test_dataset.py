import numpy as np
import pytest

import imzdesk.data.dataset as dataset_module
from imzdesk.core import PairedImage
from imzdesk.data import Dataset, DatasetManifest


class FakeWSI:
    def __init__(self, filepath):
        self.filepath = filepath


class FakeMSI:
    def __init__(self, filepath):
        self.filepath = filepath

    def derived_path(self, suffix):
        return self.filepath.parent / '.imzDesk' / f'{self.filepath.stem}{suffix}'


def write_manifest(workspace, kind, samples, dataset_id='dataset'):
    manifest = DatasetManifest(
        id=dataset_id,
        name='Training Dataset',
        kind=kind,
        splits={'train': samples, 'test': []},
    )
    manifest.to_workspace(workspace)
    return manifest


@pytest.fixture(autouse=True)
def fake_image_classes(monkeypatch):
    monkeypatch.setattr(dataset_module, 'WSI', FakeWSI)
    monkeypatch.setattr(dataset_module, 'MSI', FakeMSI)


@pytest.mark.parametrize(('kind', 'field', 'expected_type'), [
    ('wsi', 'wsi', FakeWSI),
    ('msi', 'msi', FakeMSI),
])
def test_dataset_loads_single_modality_samples(tmp_path, kind, field, expected_type):
    path = tmp_path / f'sample.{"ndpi" if kind == "wsi" else "imzML"}'
    path.touch()
    write_manifest(tmp_path, kind, [{'id': 'sample', field: path.name}])

    dataset = Dataset(tmp_path, 'dataset')

    assert len(dataset) == 1
    assert isinstance(dataset[0], expected_type)
    assert dataset[0].filepath == path


def test_dataset_loads_paired_sample_and_registration(tmp_path):
    wsi_path = tmp_path / 'sample.ndpi'
    msi_path = tmp_path / 'sample.imzML'
    wsi_path.touch()
    msi_path.touch()
    write_manifest(tmp_path, 'paired', [{
        'id': 'sample',
        'wsi': wsi_path.name,
        'msi': msi_path.name,
    }])
    registration_path = tmp_path / '.imzDesk' / f'sample.{wsi_path.name}.transform.npy'
    np.save(registration_path, np.eye(3), allow_pickle=False)

    sample = Dataset(tmp_path, 'dataset')[0]

    assert isinstance(sample, PairedImage)
    assert isinstance(sample.wsi, FakeWSI)
    assert isinstance(sample.msi, FakeMSI)
    np.testing.assert_array_equal(sample.registration.matrix, np.eye(3))


def test_dataset_loads_paired_sample_without_optional_registration(tmp_path):
    wsi_path = tmp_path / 'sample.ndpi'
    msi_path = tmp_path / 'sample.imzML'
    wsi_path.touch()
    msi_path.touch()
    write_manifest(tmp_path, 'paired', [{
        'id': 'sample',
        'wsi': wsi_path.name,
        'msi': msi_path.name,
    }])

    sample = Dataset(tmp_path, 'dataset')[0]

    assert isinstance(sample, PairedImage)
    assert sample.registration is None


def test_dataset_applies_transform(tmp_path):
    path = tmp_path / 'sample.ndpi'
    path.touch()
    write_manifest(tmp_path, 'wsi', [{'id': 'sample', 'wsi': path.name}])

    dataset = Dataset(tmp_path, 'dataset', transform=lambda image: image.filepath.name)

    assert dataset[0] == 'sample.ndpi'


def test_dataset_rejects_missing_manifest(tmp_path):
    with pytest.raises(FileNotFoundError, match='manifest does not exist'):
        Dataset(tmp_path, 'missing')


def test_dataset_rejects_missing_workspace(tmp_path):
    missing = tmp_path / 'not-created'

    with pytest.raises(NotADirectoryError, match='Workspace does not exist'):
        Dataset(missing, 'dataset')


def test_dataset_rejects_unknown_split(tmp_path):
    write_manifest(tmp_path, 'wsi', [])

    with pytest.raises(KeyError, match='Unknown split'):
        Dataset(tmp_path, 'dataset', split='validation')


def test_dataset_rejects_missing_sample_file(tmp_path):
    write_manifest(tmp_path, 'wsi', [{'id': 'missing', 'wsi': 'missing.ndpi'}])

    with pytest.raises(FileNotFoundError, match='Sample file does not exist'):
        Dataset(tmp_path, 'dataset')[0]


def test_dataset_reports_missing_modality_with_sample_id(tmp_path):
    write_manifest(tmp_path, 'wsi', [{'id': 'incomplete'}])

    with pytest.raises(ValueError, match="Sample 'incomplete' has no WSI path"):
        Dataset(tmp_path, 'dataset')[0]
