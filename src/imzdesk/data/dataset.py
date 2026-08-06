from pathlib import Path

import numpy as np

from imzdesk.core import PairedImage, Transform
from imzdesk.io import MSI, WSI
from .manifest import DatasetManifest


class Dataset:
    def __init__(
        self,
        workspace,
        dataset_id,
        split='train',
        transform=None,
    ):
        """
        Initialize a map-style dataset from an imzDesk manifest.

        Parameters
        ----------
        workspace : pathlib.Path or str
            Root workspace containing the dataset manifest and sample files.
        dataset_id : str
            Identifier of the manifest to load.
        split : str, default='train'
            Manifest split exposed by this dataset.
        transform : callable, optional
            Transform applied to each loaded sample.

        Attributes
        ----------
        manifest : DatasetManifest
            Loaded dataset manifest.
        samples : list of dict
            Records belonging to the selected split.

        Raises
        ------
        NotADirectoryError
            If ``workspace`` is not an existing directory.
        FileNotFoundError
            If the requested manifest does not exist.
        KeyError
            If the requested split is absent from the manifest.
        """
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
        """
        Return the number of samples in the selected split.
        """
        return len(self.samples)

    def __getitem__(self, index):
        """
        Load and transform a sample by index.
        """
        record = self.samples[index]
        sample = self._load_sample(record)
        return sample if self.transform is None else self.transform(sample)

    def _load_sample(self, record):
        """
        Construct the image object or registered pair for a sample record.
        """
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

    def _sample_path(self, record, modality):
        """
        Resolve and validate one modality path from a sample record.

        Parameters
        ----------
        record : dict
            Manifest sample record.
        modality : str
            Modality key to resolve.

        Returns
        -------
        pathlib.Path
            Existing sample file path.
        """
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
    def _load_registration(msi, wsi):
        """
        Load a saved MSI-to-WSI registration transform when available.

        Parameters
        ----------
        msi : MSI
            Moving mass spectrometry image.
        wsi : WSI
            Fixed whole-slide image.

        Returns
        -------
        Transform or None
            Stored transform, or ``None`` when the pair is not registered.
        """
        path = msi.derived_path(f'.{wsi.filepath.name}.transform.npy')
        if not path.is_file():
            return None
        return Transform(np.load(path, allow_pickle=False))
