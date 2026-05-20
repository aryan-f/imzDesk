import os
from pathlib import Path
from typing import Callable

import h5py
import hdf5plugin
import numpy as np
from pyimzml.ImzMLParser import ImzMLParser
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA

from imz5 import IMZ5
from imz5.schema import A
from ..utils import asynced, stashed


def convert(source: Path, destination: Path, cancelled: Callable[[], bool] = lambda: False):
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

            yield {'phase': 'closing'}

            check_cancelled()

        os.replace(temporary, destination)

    except Exception:
        if temporary.exists():
            os.unlink(temporary)
        raise


@asynced
@stashed
def coordinates_2d(filepath: Path, file: IMZ5):
    coords = file.scatter(file.coordinates[:])
    coords = coords[0, :, :, :2]
    return coords[0, :, 0], coords[:, 0, 1]


@asynced
@stashed
def tic_2d(filepath: Path, file: IMZ5):
    vals = file.values[:]
    ids = file.ids[:]
    num_pixels = len(file.offsets) - 1
    tic = np.bincount(ids, weights=vals, minlength=num_pixels)
    return file.scatter(tic).squeeze()


@asynced
@stashed
def ion_2d(filepath: Path, file: IMZ5, mz: float, tolerance: float):
    point_indices = file.mask_ion(mz, tolerance)
    if not len(point_indices):
        return np.zeros(file.shape).squeeze()
    num_pixels = len(file.offsets) - 1
    pixel_ids = file.ids[:][point_indices]
    point_vals = file.values[:][point_indices]
    per_pixel = np.bincount(pixel_ids, weights=point_vals, minlength=num_pixels)
    return file.scatter(per_pixel).squeeze()


@stashed
def pca_2d_raw(filepath: Path, file: IMZ5, bin_width, n_components, normalization):
    matrix, bins = file.binned(bin_width, normalization)
    pca = PCA(n_components=max(n_components, 3))
    return pca.fit_transform(matrix)


@asynced
def pca_2d(filepath: Path, file: IMZ5, bin_width, n_components, normalization):
    scores = pca_2d_raw(filepath, file=file, bin_width=bin_width, n_components=n_components, normalization=normalization)
    lo = scores.min(axis=0)
    hi = scores.max(axis=0)
    hi[hi == lo] = 1
    scores = (scores - lo) / (hi - lo)
    return file.scatter(scores).squeeze()


@asynced
@stashed
def kmn_2d(filepath: Path, file: IMZ5, bin_width, n_components, normalization, n_clusters):
    scores = pca_2d_raw(filepath, file=file, bin_width=bin_width, n_components=n_components, normalization=normalization)
    labels = KMeans(n_clusters=n_clusters, n_init='auto').fit_predict(scores).astype(np.int32)
    return file.scatter(labels).squeeze()
    

async def image_2d(filepath, mode, executor, **kwargs):
    with (IMZ5(filepath) as file):
        depth, height, width = file.shape
        assert depth == 1, f'Expected a 2D image. Got {file.shape}'
        coords = await coordinates_2d(filepath, file=file, executor=executor)
        match mode:
            case 'tic':
                return await tic_2d(
                    filepath,
                    file=file,
                    executor=executor
                ), coords
            case 'ion':
                return await ion_2d(
                    filepath,
                    file=file,
                    mz=kwargs['targetIon'],
                    tolerance=kwargs['tolerance'],
                    executor=executor
                ), coords
            case 'pca':
                return await pca_2d(
                    filepath,
                    file=file,
                    bin_width=kwargs['binWidth'],
                    n_components=kwargs['numComponents'],
                    normalization=kwargs['normalization'],
                    executor=executor
                ), coords
            case 'kmn':
                return await kmn_2d(
                    filepath,
                    file=file,
                    bin_width=kwargs['binWidth'],
                    n_components=kwargs['numComponents'],
                    normalization=kwargs['normalization'],
                    n_clusters=kwargs['numClusters'],
                    executor=executor
                ), coords
            case other:
                # Unlikely to hit; schema will reject such requests. regardless:
                raise NotImplementedError


@asynced
@stashed
def spectrum_2d(filepath, x_min, x_max, y_min, y_max, precision):
    with IMZ5(filepath) as file:
        depth, height, width = file.shape
        assert depth == 1, f'Expected a 2D image. Got {file.shape}'
        locs, vals = file.spectrum(x_min, x_max, y_min, y_max, precision=precision)
        return {'mz': locs.tolist(), 'intensity': vals.tolist()}
