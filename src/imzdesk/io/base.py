import abc
import pathlib
import typing

import yaml

from imzdesk.core.metadata import Metadata


class ImageBase(abc.ABC):
    metadata_class: typing.ClassVar[type[Metadata]]
    extensions: typing.ClassVar[tuple[str, ...]]

    def __init__(self, filepath):
        """
        Base class for image files.

        Parameters
        ----------
        filepath: pathlib.Path or str
            The path to the image file.
        """
        self.filepath = pathlib.Path(filepath)
        self._metadata = None
        self._tags = None

    @property
    def metadata(self):
        if self._metadata is None:
            self._metadata = self.read_metadata(self.filepath)
        return self._metadata

    @metadata.setter
    def metadata(self, value):
        self._metadata = value

    @property
    def metadata_path(self) -> pathlib.Path:
        return self.derived_path('.meta.yaml')

    @property
    def tags(self) -> list[str]:
        if self._tags is None:
            self._tags = self.read_tags(self.filepath)
        return self._tags

    @tags.setter
    def tags(self, value):
        self._tags = value

    @property
    def tags_path(self) -> pathlib.Path:
        return self.derived_path('.tags.yaml')

    @classmethod
    def read_metadata(cls, filepath):
        metadata_path = cls.derived_path_for(filepath, '.meta.yaml')
        try:
            return cls.metadata_class.from_file(metadata_path)
        except FileNotFoundError:
            metadata = cls.init_metadata(filepath)
            metadata.to_file(metadata_path)
            return metadata

    @classmethod
    def write_metadata(cls, filepath, metadata: Metadata) -> Metadata:
        metadata_path = cls.derived_path_for(filepath, '.meta.yaml')
        metadata.to_file(metadata_path)
        return metadata

    @classmethod
    def read_tags(cls, filepath) -> list[str]:
        tags_path = cls.derived_path_for(filepath, '.tags.yaml')
        if not tags_path.exists():
            return []
        with open(tags_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        if data is None:
            return []
        return list(data)

    @classmethod
    def write_tags(cls, filepath, tags: list[str]) -> list[str]:
        tags_path = cls.derived_path_for(filepath, '.tags.yaml')
        tags_path.parent.mkdir(parents=True, exist_ok=True)
        with open(tags_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(tags, f, sort_keys=False)
        return tags

    @classmethod
    @abc.abstractmethod
    def init_metadata(cls, filepath) -> Metadata:
        """
        Called when no metadata file is found.

        Parameters
        ----------
        filepath: pathlib.Path or str
            The path to the image file.

        Returns
        -------
        metadata: Metadata
            Filled metadata object of a subclass appropriate for the image file.
        """
        pass

    def flush_metadata(self):
        self.metadata.to_file(self.metadata_path)

    def flush_tags(self):
        self.write_tags(self.filepath, self.tags)

    def derived_path(self, suffix: str) -> pathlib.Path:
        return self.derived_path_for(self.filepath, suffix)

    @staticmethod
    def derived_path_for(filepath, suffix: str) -> pathlib.Path:
        filepath = pathlib.Path(filepath)
        return filepath.parent / '.imzDesk' / f'{filepath.stem}{suffix}'
