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
        self.metadata_path = self.derived_path('.meta.yaml')
        try:
            self.metadata = self.metadata_class.from_file(self.metadata_path)
        except FileNotFoundError:
            self.metadata = self.init_metadata()

    @abc.abstractmethod
    def init_metadata(self) -> Metadata:
        """
        Called when no metadata file is found.

        Returns
        -------
        metadata: Metadata
            Filled metadata object of a subclass appropriate for the image file.
        """
        pass

    def dump_metadata(self):
        self.metadata.to_file(self.metadata_path)

    def derived_path(self, suffix: str) -> pathlib.Path:
        return self.filepath.parent / '.imzDesk' / f'{self.filepath.stem}{suffix}'
