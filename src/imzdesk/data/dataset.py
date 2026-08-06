from collections.abc import Callable
from pathlib import Path

import numpy as np

from imzdesk.core import PairedImage, Transform
from imzdesk.io import MSI, WSI

from .manifest import DatasetManifest


class Dataset:
    """Map-style dataset backed by an imzDesk dataset manifest."""

    def __init__(
        self,
        workspace: Path | str,
        dataset_id: str,
        split: str = 'train',
        transform: Callable | None = None,
    ):
        self.workspace = Path(workspace).expanduser().resolve()
        if not self.workspace.is_dir():
            raise NotADirectoryError(f'Workspace does not exist: {self.workspace}')

        manifest_path = DatasetManifest.path(self.workspace, dataset_id)
        if not manifest_path.is_file():
            raise FileNotFoundError(f'Dataset manifest does not exist: {manifest_path}')
        self.manifest = DatasetManifest.from_workspace(self.workspace, dataset_id)
        if split not in self.manifest.splits:
            raise KeyError(f'Unknown split {split!r} for dataset {dataset_id!r}.')

        self.dataset_id = dataset_id
        self.split = split
        self.transform = transform
        self.samples = self.manifest.splits[split]

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, index):
        record = self.samples[index]
        sample = self._load_sample(record)
        return sample if self.transform is None else self.transform(sample)

    def _load_sample(self, record):
        match self.manifest.kind:
            case 'wsi':
                return WSI(self._sample_path(record, 'wsi'))
            case 'msi':
                return MSI(self._sample_path(record, 'msi'))
            case 'paired':
                wsi = WSI(self._sample_path(record, 'wsi'))
                msi = MSI(self._sample_path(record, 'msi'))
                registration = self._load_registration(msi, wsi)
                return PairedImage(wsi=wsi, msi=msi, registration=registration)
            case other:
                raise ValueError(f'Unknown dataset kind: {other}')

    def _sample_path(self, record, modality: str) -> Path:
        try:
            relative_path = record[modality]
        except KeyError as exception:
            raise ValueError(
                f'Sample {record.get("id", "<unknown>")!r} has no {modality.upper()} path.'
            ) from exception
        path = self.workspace / relative_path
        if not path.is_file():
            raise FileNotFoundError(f'Sample file does not exist: {path}')
        return path

    @staticmethod
    def _load_registration(msi: MSI, wsi: WSI) -> Transform | None:
        path = msi.derived_path(f'.{wsi.filepath.name}.transform.npy')
        if not path.is_file():
            return None
        return Transform(np.load(path, allow_pickle=False))
