import abc
import pathlib
import typing

import yaml

from imzdesk.core.metadata import Metadata
from imzdesk.core.workspace import derived_path


class ImageBase(abc.ABC):
    metadata_class: typing.ClassVar[type[Metadata]]
    extensions: typing.ClassVar[tuple[str, ...]]

    def __init__(self, filepath):
        """
        Base class for image files.

        Parameters
        ----------
        filepath : pathlib.Path or str
            The path to the image file.
        """
        self.filepath = pathlib.Path(filepath)
        self._metadata = None
        self._tags = None
        self._annotations = None

    @property
    def metadata(self):
        """
        Return metadata, loading or initializing it on first access.
        """
        if self._metadata is None:
            self._metadata = self.read_metadata(self.filepath)
        return self._metadata

    @metadata.setter
    def metadata(self, value):
        """
        Replace the in-memory metadata value.
        """
        self._metadata = value

    @property
    def metadata_path(self):
        """
        Return the sidecar path containing image metadata.

        Returns
        -------
        pathlib.Path
            Metadata YAML path.
        """
        return self.derived_path('.meta.yaml')

    @property
    def tags(self):
        """
        Return image tags, loading them on first access.

        Returns
        -------
        list of str
            Current image tags.
        """
        if self._tags is None:
            self._tags = self.read_tags(self.filepath)
        return self._tags

    @tags.setter
    def tags(self, value):
        """
        Replace the in-memory image tags.
        """
        self._tags = value

    @property
    def tags_path(self):
        """
        Return the sidecar path containing image tags.

        Returns
        -------
        pathlib.Path
            Tags YAML path.
        """
        return self.derived_path('.tags.yaml')

    @property
    def annotations(self):
        """
        Return image annotations, loading them on first access.

        Returns
        -------
        list of dict
            Current image annotations.
        """
        if self._annotations is None:
            self._annotations = self.read_annotations(self.filepath)
        return self._annotations

    @annotations.setter
    def annotations(self, value):
        """
        Replace the in-memory image annotations.
        """
        self._annotations = value

    @property
    def annotations_path(self):
        """
        Return the sidecar path containing image annotations.

        Returns
        -------
        pathlib.Path
            Annotations YAML path.
        """
        return self.derived_path('.annotations.yaml')

    @classmethod
    def read_metadata(cls, filepath):
        """
        Read metadata from its sidecar or initialize it from the image.
        """
        metadata_path = cls.derived_path_for(filepath, '.meta.yaml')
        try:
            return cls.metadata_class.from_file(metadata_path)
        except FileNotFoundError:
            metadata = cls.init_metadata(filepath)
            metadata.to_file(metadata_path)
            return metadata

    @classmethod
    def write_metadata(cls, filepath, metadata):
        """
        Write image metadata to its sidecar and return it.

        Parameters
        ----------
        filepath : pathlib.Path or str
            Source image path.
        metadata : Metadata
            Metadata value to persist.

        Returns
        -------
        Metadata
            Persisted metadata value.
        """
        metadata_path = cls.derived_path_for(filepath, '.meta.yaml')
        metadata.to_file(metadata_path)
        return metadata

    @classmethod
    def read_tags(cls, filepath):
        """
        Read image tags from their YAML sidecar.

        Parameters
        ----------
        filepath : pathlib.Path or str
            Source image path.

        Returns
        -------
        list of str
            Stored tags, or an empty list when no sidecar exists.
        """
        tags_path = cls.derived_path_for(filepath, '.tags.yaml')
        if not tags_path.exists():
            return []
        with open(tags_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        if data is None:
            return []
        return list(data)

    @classmethod
    def write_tags(cls, filepath, tags):
        """
        Write image tags to their YAML sidecar and return them.

        Parameters
        ----------
        filepath : pathlib.Path or str
            Source image path.
        tags : list of str
            Tags to persist.

        Returns
        -------
        list of str
            Persisted tags.
        """
        tags_path = cls.derived_path_for(filepath, '.tags.yaml')
        tags_path.parent.mkdir(parents=True, exist_ok=True)
        with open(tags_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(tags, f, sort_keys=False)
        return tags

    @classmethod
    def read_annotations(cls, filepath):
        """
        Read image annotations from their YAML sidecar.

        Parameters
        ----------
        filepath : pathlib.Path or str
            Source image path.

        Returns
        -------
        list of dict
            Stored annotations, or an empty list when no sidecar exists.
        """
        annotations_path = cls.derived_path_for(filepath, '.annotations.yaml')
        if not annotations_path.exists():
            return []
        with open(annotations_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        if data is None:
            return []
        if isinstance(data, list):
            return list(data)
        return list(data.get('annotations', []))

    @classmethod
    def write_annotations(cls, filepath, annotations):
        """
        Write image annotations to their YAML sidecar and return them.

        Parameters
        ----------
        filepath : pathlib.Path or str
            Source image path.
        annotations : list of dict
            Annotations to persist.

        Returns
        -------
        list of dict
            Persisted annotations.
        """
        annotations_path = cls.derived_path_for(filepath, '.annotations.yaml')
        annotations_path.parent.mkdir(parents=True, exist_ok=True)
        with open(annotations_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(annotations, f, sort_keys=False)
        return annotations

    @classmethod
    @abc.abstractmethod
    def init_metadata(cls, filepath):
        """
        Initialize metadata when its sidecar is absent.

        Parameters
        ----------
        filepath : pathlib.Path or str
            The path to the image file.

        Returns
        -------
        metadata : Metadata
            Filled metadata object of a subclass appropriate for the image file.
        """
        pass

    def flush_metadata(self):
        """
        Persist the current in-memory metadata.
        """
        self.metadata.to_file(self.metadata_path)

    def flush_tags(self):
        """
        Persist the current in-memory image tags.
        """
        self.write_tags(self.filepath, self.tags)

    def flush_annotations(self):
        """
        Persist the current in-memory image annotations.
        """
        self.write_annotations(self.filepath, self.annotations)

    def derived_path(self, suffix):
        """
        Return the workspace path for an artifact derived from this image.

        Parameters
        ----------
        suffix : str
            Artifact suffix appended to the image stem.

        Returns
        -------
        pathlib.Path
            Derived artifact path.
        """
        return self.derived_path_for(self.filepath, suffix)

    @staticmethod
    def derived_path_for(filepath, suffix):
        """
        Return the workspace path for an artifact derived from a file.

        Parameters
        ----------
        filepath : pathlib.Path or str
            Source file path.
        suffix : str
            Artifact suffix appended to the file stem.

        Returns
        -------
        pathlib.Path
            Derived artifact path.
        """
        return derived_path(filepath, suffix)
