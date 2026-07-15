import abc
import pathlib
import typing

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

    def dump_metadata(self):
        self.metadata.to_file(self.metadata_path)

    def derived_path(self, suffix: str) -> pathlib.Path:
        return self.derived_path_for(self.filepath, suffix)

    @staticmethod
    def derived_path_for(filepath, suffix: str) -> pathlib.Path:
        filepath = pathlib.Path(filepath)
        return filepath.parent / '.imzDesk' / f'{filepath.stem}{suffix}'
