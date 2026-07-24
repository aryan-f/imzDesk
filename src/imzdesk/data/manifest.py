from pathlib import Path
from typing import Literal
from uuid import uuid4

import yaml
from pydantic import BaseModel, Field

from imzdesk.core.workspace import workspace_path


class DatasetManifest(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    name: str
    kind: Literal['wsi', 'msi', 'paired']
    splits: dict[str, list[dict[str, str]]] = Field(default_factory=lambda: {'train': []})

    @classmethod
    def directory(cls, root: Path | str) -> Path:
        return workspace_path(root, 'datasets')

    @classmethod
    def path(cls, root: Path | str, dataset_id: str) -> Path:
        return cls.directory(root) / f'{dataset_id}.yaml'

    @classmethod
    def from_workspace(cls, root: Path | str, dataset_id: str):
        with open(cls.path(root, dataset_id), 'r', encoding='utf-8') as f:
            return cls.model_validate(yaml.safe_load(f))

    @classmethod
    def list_workspace(cls, root: Path | str):
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

    def to_workspace(self, root: Path | str) -> None:
        directory = self.directory(root)
        directory.mkdir(parents=True, exist_ok=True)
        with open(self.path(root, self.id), 'w', encoding='utf-8') as f:
            yaml.safe_dump(self.model_dump(), f, sort_keys=False)

    @classmethod
    def delete_workspace(cls, root: Path | str, dataset_id: str) -> None:
        path = cls.path(root, dataset_id)
        if path.exists():
            path.unlink()
