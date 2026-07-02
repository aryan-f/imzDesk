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
        self.metadata_path = None
        self.metadata = None

    def resolve_metadata(self):
        self.metadata_path = self.derived_path(self.filepath, '.meta.yaml')
        try:
            self.metadata = self.metadata_class.from_file(self.metadata_path)
        except FileNotFoundError:
            self.metadata = self.initialize_metadata()

    @abc.abstractmethod
    def initialize_metadata(self) -> Metadata:
        """
        Called when no metadata file is found.

        Returns
        -------
        metadata: Metadata
            Filled metadata object of a subclass appropriate for the image file.
        """
        pass

    def write_metadata_to_disk(self):
        self.metadata.to_file(self.metadata_path)

    @classmethod
    def derived_path(cls, path: pathlib.Path, suffix: str) -> pathlib.Path:
        return path.parent / '.imzDesk' / f'{path.stem}{suffix}'
