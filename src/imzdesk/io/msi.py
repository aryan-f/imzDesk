import os
import warnings
from functools import cached_property
from pathlib import Path

import h5py
import numpy as np
from lxml import etree
from pyimzml.ImzMLParser import ImzMLParser, PortableSpectrumReader

from .base import ImageBase
from ..core import metadata

# Suppress the specific pyimzml ontology naming warning
warnings.filterwarnings('ignore', message='Accession .* found with incorrect name.*', category=UserWarning)


class MSIMetadata(metadata.Metadata):
    """
    Mass spectrometry image metadata.
    """

    pass


class MSI(ImageBase):
    metadata_class = MSIMetadata
    extensions = ('.imzML',)

    def __init__(self, filepath, ibd_path=None, cache_portable=True):
        """
        Initialize a mass spectrometry image reader.

        The class is a wrapper on the ``pyimzml`` library and its components that avoids parsing the XML file on every
        access in order to speed up processing. Contained metadata (accessions) are currently discarded in the process.

        The class assumes that the imzML is 2D. It assumes that across all coordinates, ``z==1``.

        Parameters
        ----------
        filepath : pathlib.Path or str
            The path to the `.imzML` file.
        ibd_path : pathlib.Path or str, optional
            The path to the `.ibd` file. If not specified, it will be inferred from the ``imzml_path``.
        cache_portable : bool, default=True
            Whether to cache the minimal set of data required for reading, avoiding XML parsing on the next access.
        """
        super().__init__(filepath)

        self.ibd_path = Path(ibd_path) if ibd_path is not None else self.filepath.with_suffix('.ibd')

        self.cache_path = self.derived_path('.h5')
        if self.cache_path.exists():
            self.reader = self.from_cache()
        else:
            parser = ImzMLParser(self.filepath, ibd_file=ibd_path)
            self.reader = parser.portable_spectrum_reader()
            if cache_portable:
                self.cache()

        self.ibd_file = None  # Lazy

    @classmethod
    def init_metadata(cls, filepath):
        """
        Extract image dimensions and spatial resolution from imzML metadata.

        Parameters
        ----------
        filepath : pathlib.Path
            imzML file path.

        Returns
        -------
        MSIMetadata
            Extracted image metadata.
        """
        # Even though ``ImzMLParser.imzmldict`` contains these properties, the library discards the units which could
        # cause serious problems. We'll have to parse it again to extract the relevant accessions.
        (width, none), (height, none), (x, xu), (y, yu) = get_cvparams_by_accession(
            filepath,
            'IMS:1000042',
            'IMS:1000043',
            'IMS:1000046',
            'IMS:1000047'
        )
        return MSIMetadata(
            width=int(width),
            height=int(height),
            mpp=metadata.Dimensions(
                x=as_microns(x, xu),
                y=as_microns(y, yu),
            ),
        )

    def from_cache(self):
        """
        Construct a portable spectrum reader from the HDF5 cache.
        """
        with h5py.File(self.cache_path, 'r') as f:
            return PortableSpectrumReader(
                coordinates=f['coordinates'][:],
                mzPrecision=f.attrs['mzPrecision'],
                mzOffsets=f['mzOffsets'][:],
                mzLengths=f['mzLengths'][:],
                intensityPrecision=f.attrs['intensityPrecision'],
                intensityOffsets=f['intensityOffsets'][:],
                intensityLengths=f['intensityLengths'][:],
            )

    def cache(self):
        """
        Persist the portable spectrum reader fields to HDF5.
        """
        os.makedirs(self.cache_path.parent, exist_ok=True)
        with h5py.File(self.cache_path, 'w') as f:
            f.create_dataset('coordinates', data=np.asarray(self.reader.coordinates))
            f.attrs['mzPrecision'] = self.reader.mzPrecision
            f.create_dataset('mzOffsets', data=np.asarray(self.reader.mzOffsets))
            f.create_dataset('mzLengths', data=np.asarray(self.reader.mzLengths))
            f.attrs['intensityPrecision'] = self.reader.intensityPrecision
            f.create_dataset('intensityOffsets', data=np.asarray(self.reader.intensityOffsets))
            f.create_dataset('intensityLengths', data=np.asarray(self.reader.intensityLengths))

    def __enter__(self):
        """
        Open the binary spectrum file for indexed reads.
        """
        self.ibd_file = open(self.ibd_path, 'rb')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Close the binary spectrum file.
        """
        self.ibd_file.close()

    def __len__(self):
        """
        Return the number of measured spectra.
        """
        return len(self.reader.coordinates)

    @cached_property
    def coordinates(self):
        """
        Return the measured imzML coordinates as an array.
        """
        return np.asarray(self.reader.coordinates)

    def __getitem__(self, index):
        """
        Read the spectrum at a specified index from the ``.ibd`` file.

        Parameters
        ----------
        index : int
            Target spectrum.

        Raises
        ------
        AssertionError
            If the ``.ibd`` file has not been opened.

        Returns
        -------
        mz : numpy.ndarray
            m/z ratios.
        vals : numpy.ndarray
            Intensities.
        """
        assert self.ibd_file is not None, 'Open the file first.'
        return self.reader.read_spectrum_from_file(self.ibd_file, index)

    def at(self, x, y):
        """
        Read the spectrum at specified coordinates from the ``.ibd`` file.

        Parameters
        ----------
        x, y : int
            Coordinates.

        Raises
        ------
        AssertionError
            If the ``.ibd`` file has not been opened.
        ValueError
            If the coordinates do not exist in file.

        Returns
        -------
        mz : numpy.ndarray
            m/z ratios.
        vals : numpy.ndarray
            Intensities.
        """
        matches, = np.where((self.coordinates[:, 0] == x) & (self.coordinates[:, 1] == y))

        if matches.size == 0:
            raise ValueError(f"Coordinates (x={x}, y={y}) not found in the dataset.")

        index = matches[0]
        return self[index]


def get_cvparams_by_accession(imzml_path, *accessions):
    """
    Return the raw attributes of the first <cvParam> with a given accession.

    Parameters
    ----------
    imzml_path : pathlib.Path
        The path to the ``.imzML`` file.
    *accessions : str
        Target accessions to extract.

    Yields
    ------
    value : str
        The ``value`` attribute.
    unit : str or None
        The ``unitName`` attribute, if available.
    """
    parser = etree.XMLParser(recover=True, huge_tree=True, remove_blank_text=True,)
    tree = etree.parse(imzml_path, parser)
    for accession in accessions:
        matches = tree.xpath(
            ".//mzml:cvParam[@accession=$accession]",
            namespaces={"mzml": "http://psi.hupo.org/ms/mzml",},
            accession=accession,
        )
        if not matches:
            yield None
            continue
        match, = matches
        yield match.attrib['value'], match.attrib.get('unitAccession')


def as_microns(value, unit):
    """
    Convert a value from the specified unit to microns.

    Parameters
    ----------
    value : str
        Floating-point value.
    unit : str
        Units Ontology accession.

    Returns
    -------
    value : float
        In microns.
    """
    multiplier = {
        'UO:0000015': 10_000.0,  # centimeter
        'UO:0000016': 1_000.0,  # millimeter
        'UO:0000017': 1.0,  # micrometer / micron / um
        'UO:0000018': 0.001,  # nanometer
        'UO:0000019': 0.0001,  # angstrom
    }
    if unit not in multiplier:
        raise NotImplementedError
    return float(value) * multiplier[unit]
