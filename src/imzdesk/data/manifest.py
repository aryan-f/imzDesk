from typing import Literal
from uuid import uuid4

import yaml
from pydantic import BaseModel, Field

from imzdesk.core.workspace import workspace_path


class DatasetManifest(BaseModel):
    """
    Describe dataset identity, modality, and split membership.
    """

    id: str = Field(default_factory=lambda: uuid4().hex)
    name: str
    kind: Literal['wsi', 'msi', 'paired']
    splits: dict[str, list[dict[str, str]]] = Field(default_factory=lambda: {'train': []})

    @classmethod
    def directory(cls, root):
        """
        Return the directory containing manifests for a workspace.

        Parameters
        ----------
        root : pathlib.Path or str
            Workspace root.

        Returns
        -------
        pathlib.Path
            Dataset manifest directory.
        """
        return workspace_path(root, 'datasets')

    @classmethod
    def path(cls, root, dataset_id):
        """
        Return the YAML path for a dataset manifest.

        Parameters
        ----------
        root : pathlib.Path or str
            Workspace root.
        dataset_id : str
            Dataset identifier.

        Returns
        -------
        pathlib.Path
            Dataset manifest path.
        """
        return cls.directory(root) / f'{dataset_id}.yaml'

    @classmethod
    def from_workspace(cls, root, dataset_id):
        """
        Load and validate one dataset manifest from a workspace.

        Parameters
        ----------
        root : pathlib.Path or str
            Workspace root.
        dataset_id : str
            Dataset identifier.

        Returns
        -------
        DatasetManifest
            Validated manifest.
        """
        with open(cls.path(root, dataset_id), 'r', encoding='utf-8') as f:
            return cls.model_validate(yaml.safe_load(f))

    @classmethod
    def list_workspace(cls, root):
        """
        Load all dataset manifests found in a workspace.

        Parameters
        ----------
        root : pathlib.Path or str
            Workspace root.

        Returns
        -------
        list of DatasetManifest
            Valid manifests sorted by filename.
        """
        directory = cls.directory(root)
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            return []
        manifests = []
        for path in sorted(directory.glob('*.yaml')):
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            if data:
                manifests.append(cls.model_validate(data))
        return manifests

    def to_workspace(self, root):
        """
        Write this dataset manifest to a workspace.

        Parameters
        ----------
        root : pathlib.Path or str
            Workspace root.
        """
        directory = self.directory(root)
        directory.mkdir(parents=True, exist_ok=True)
        with open(self.path(root, self.id), 'w', encoding='utf-8') as f:
            yaml.safe_dump(self.model_dump(), f, sort_keys=False)

    @classmethod
    def delete_workspace(cls, root, dataset_id):
        """
        Delete a dataset manifest from a workspace when it exists.

        Parameters
        ----------
        root : pathlib.Path or str
            Workspace root.
        dataset_id : str
            Dataset identifier.
        """
        path = cls.path(root, dataset_id)
        if path.exists():
            path.unlink()
