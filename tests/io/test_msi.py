import pytest
import numpy as np

import imzdesk.io.msi as msi_module
from imzdesk.io import MSI
from imzdesk.io.msi import as_microns, get_cvparams_by_accession


class FakeReader:
    def __init__(self):
        self.coordinates = np.array([[1, 2], [3, 4]])
        self.mzPrecision = 'float64'
        self.mzOffsets = np.array([0, 16])
        self.mzLengths = np.array([2, 1])
        self.intensityPrecision = 'float32'
        self.intensityOffsets = np.array([24, 32])
        self.intensityLengths = np.array([2, 1])
        self.reads = []

    def read_spectrum_from_file(self, file, index):
        self.reads.append((file.name, index))
        return np.array([100.0 + index]), np.array([10.0 + index])


class FakeParser:
    reader = FakeReader()

    def __init__(self, filepath, ibd_file=None):
        self.filepath = filepath
        self.ibd_file = ibd_file

    def portable_spectrum_reader(self):
        return self.reader


def test_as_microns_converts_known_units():
    assert as_microns('2', 'UO:0000015') == 20_000
    assert as_microns('2', 'UO:0000016') == 2_000
    assert as_microns('2', 'UO:0000017') == 2
    assert as_microns('2', 'UO:0000018') == 0.002
    assert as_microns('2', 'UO:0000019') == 0.0002


def test_as_microns_rejects_unknown_unit():
    with pytest.raises(NotImplementedError):
        as_microns('1', 'unknown')


def test_get_cvparams_by_accession_reads_values_and_units(tmp_path):
    path = tmp_path / 'sample.imzML'
    path.write_text(
        '''<?xml version="1.0" encoding="UTF-8"?>
        <mzML xmlns="http://psi.hupo.org/ms/mzml">
          <cvParam accession="IMS:1000042" value="12" />
          <cvParam accession="IMS:1000046" value="25" unitAccession="UO:0000017" />
        </mzML>
        ''',
        encoding='utf-8',
    )

    values = list(get_cvparams_by_accession(path, 'IMS:1000042', 'IMS:1000046', 'missing'))

    assert values == [('12', None), ('25', 'UO:0000017'), None]


def test_msi_initializes_reader_and_writes_portable_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(msi_module, 'ImzMLParser', FakeParser)
    filepath = tmp_path / 'sample.imzML'
    filepath.write_text('<mzML />', encoding='utf-8')

    image = MSI(filepath, cache_portable=True)

    assert image.ibd_path == tmp_path / 'sample.ibd'
    assert len(image) == 2
    np.testing.assert_array_equal(image.coordinates, [[1, 2], [3, 4]])
    assert image.cache_path.exists()


def test_msi_loads_reader_from_existing_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(msi_module, 'ImzMLParser', FakeParser)
    filepath = tmp_path / 'sample.imzML'
    filepath.write_text('<mzML />', encoding='utf-8')
    MSI(filepath, cache_portable=True)

    image = MSI(filepath, cache_portable=True)

    np.testing.assert_array_equal(image.reader.coordinates, [[1, 2], [3, 4]])
    assert list(image.reader.mzLengths) == [2, 1]


def test_msi_getitem_requires_context_manager(monkeypatch, tmp_path):
    monkeypatch.setattr(msi_module, 'ImzMLParser', FakeParser)
    filepath = tmp_path / 'sample.imzML'
    filepath.write_text('<mzML />', encoding='utf-8')
    image = MSI(filepath, cache_portable=False)

    with pytest.raises(AssertionError, match='Open the file first'):
        image[0]


def test_msi_at_reads_spectrum_for_matching_coordinate(monkeypatch, tmp_path):
    monkeypatch.setattr(msi_module, 'ImzMLParser', FakeParser)
    filepath = tmp_path / 'sample.imzML'
    filepath.write_text('<mzML />', encoding='utf-8')
    ibd_path = tmp_path / 'sample.ibd'
    ibd_path.write_bytes(b'fake')
    image = MSI(filepath, cache_portable=False)

    with image:
        mz, intensities = image.at(3, 4)

    np.testing.assert_allclose(mz, [101.0])
    np.testing.assert_allclose(intensities, [11.0])


def test_msi_at_rejects_missing_coordinate(monkeypatch, tmp_path):
    monkeypatch.setattr(msi_module, 'ImzMLParser', FakeParser)
    filepath = tmp_path / 'sample.imzML'
    filepath.write_text('<mzML />', encoding='utf-8')
    image = MSI(filepath, cache_portable=False)

    with pytest.raises(ValueError, match='not found'):
        image.at(0, 0)
