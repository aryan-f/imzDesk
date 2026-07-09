from __future__ import annotations

import numpy as np

from imzdesk.core import RImage
from imzdesk.io import MSI


class ToRImage:
    """
    Read an MSI into an in-memory ragged image.

    Notes
    -----
    This transform reads directly from the ``.ibd`` file using offsets already
    parsed by pyimzML.
    """

    def __call__(self, msi_image: MSI) -> RImage:
        mz_lengths = np.asarray(msi_image.reader.mzLengths, dtype=np.int64)
        intensity_lengths = np.asarray(msi_image.reader.intensityLengths, dtype=np.int64)
        pixel_offsets = np.concatenate([[0], np.cumsum(mz_lengths)])
        mz = np.empty(pixel_offsets[-1], dtype=np.float64)
        intensities = np.empty(pixel_offsets[-1], dtype=np.float32)
        ibd_bytes = np.memmap(msi_image.ibd_path, mode='r')
        mz_dtype = np.dtype(msi_image.reader.mzPrecision)
        intensity_dtype = np.dtype(msi_image.reader.intensityPrecision)
        for spectrum_index in range(len(msi_image)):
            pixel_start = pixel_offsets[spectrum_index]
            pixel_stop = pixel_offsets[spectrum_index + 1]
            mz[pixel_start:pixel_stop] = np.frombuffer(
                ibd_bytes,
                dtype=mz_dtype,
                count=mz_lengths[spectrum_index],
                offset=msi_image.reader.mzOffsets[spectrum_index],
            )
            intensities[pixel_start:pixel_stop] = np.frombuffer(
                ibd_bytes,
                dtype=intensity_dtype,
                count=intensity_lengths[spectrum_index],
                offset=msi_image.reader.intensityOffsets[spectrum_index],
            )
        return RImage(
            coordinates=msi_image.coordinates.copy(),
            positions=mz,
            values=intensities,
            offsets=pixel_offsets,
        )
