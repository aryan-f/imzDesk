import abc
from pathlib import Path

from .meta import Meta


class I(abc.ABC):

    def __init__(self, filepath, meta_path=None):
        """
        Base class for image files.

        Parameters
        ----------
        filepath: Path or str
            The path to the image file.
        meta_path: Path or str
            The path to the meta file. If not provided, it will be inferred from the file path.
        """
        self.filepath = Path(filepath)
        self.meta_path = Path(meta_path) if meta_path is not None else self.derived_path(self.filepath, '.meta.yaml')
        self.meta = Meta.from_file(self.meta_path)

    @classmethod
    def derived_path(cls, path: Path, suffix):
        return path.parent / '.imzDesk' / f'{path.stem}{suffix}'
