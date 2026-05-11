import os
from pathlib import Path
from typing import Callable

import h5py
import hdf5plugin
import numpy as np
from pyimzml.ImzMLParser import ImzMLParser

from imz5 import IMZ5
from imz5.schema import A
from ..utils import asynced, stashed


def imzML_to_imz5(source: Path, destination: Path, cancelled: Callable[[], bool] = lambda: False):
    def check_cancelled():
        if cancelled():
            raise RuntimeError('Conversion cancelled.')

    temporary = destination.with_name(destination.name + '.tmp')

    yield {'phase': 'reading'}
    check_cancelled()

    parser = ImzMLParser(source)

    coordinates = np.asarray(parser.coordinates)
    num_pixels = len(coordinates)

    offsets = np.empty(num_pixels + 1, dtype=np.int64)
    offsets[0] = 0

    yield {'phase': 'indexing', 'progress': 0}

    for i in range(num_pixels):
        check_cancelled()

        locs, vals = parser.getspectrum(i)
        offsets[i + 1] = offsets[i] + len(locs)

        if i % 100 == 0:
            yield {
                'phase': 'indexing',
                'progress': i / num_pixels,
            }

    total_points = offsets[-1]

    destination.parent.mkdir(parents=True, exist_ok=True)

    compression = hdf5plugin.Blosc(
        cname='lz4',
        clevel=5,
        shuffle=hdf5plugin.Blosc.BITSHUFFLE,
    )

    try:
        with h5py.File(temporary, 'w') as h5:
            h5.create_dataset(A.OFFSETS, data=offsets, dtype=np.int64, compression=compression)
            h5.create_dataset(A.COORDINATES, data=coordinates, dtype=np.int64, compression=compression)

            locations = h5.create_dataset(A.LOCATIONS, shape=(total_points,), dtype=np.float64, compression=compression)
            values = h5.create_dataset(A.VALUES, shape=(total_points,), dtype=np.float32, compression=compression)
            ids = h5.create_dataset(A.IDS, shape=(total_points,), dtype=np.int64, compression=compression)

            yield {'phase': 'processing', 'progress': 0}

            for i in range(num_pixels):
                check_cancelled()

                locs, vals = parser.getspectrum(i)
                start, end = offsets[i], offsets[i + 1]

                locations[start:end] = np.asarray(locs, dtype=np.float64)
                values[start:end] = np.asarray(vals, dtype=np.float32)
                ids[start:end] = i

                if i % 100 == 0:
                    yield {
                        'phase': 'processing',
                        'progress': i / num_pixels,
                    }

            yield {'phase': 'sorting'}

            check_cancelled()
            order = np.argsort(locations[:], kind='mergesort')
            h5.create_dataset(A.ORDER, data=order, dtype=np.int64, compression=compression)

        os.replace(temporary, destination)

    except Exception:
        if temporary.exists():
            os.unlink(temporary)
        raise


@asynced
@stashed
def tic_from_imz5(filepath):
    imz5 = IMZ5(filepath)
    assert imz5.ndim == 2, '3D images are not currently supported.'
    return imz5.tic()


@asynced
@stashed
def spectrum(filepath, x_min, x_max, y_min, y_max):
    imz5 = IMZ5(filepath)
    assert imz5.ndim == 2, '3D images are not currently supported.'
    loc, val = imz5.spectrum(x_min, x_max, y_min, y_max)
    return {'mz': loc.tolist(), 'intensity': val.tolist()}
