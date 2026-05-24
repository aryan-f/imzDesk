import os
import warnings
from pathlib import Path
from typing import Callable

import h5py
import hdf5plugin
import numpy as np
from pyimzml.ImzMLParser import ImzMLParser

from imz5 import IMZ5
from imz5.schema import A
from ..utils import (
    async_threaded,
    base64_png,
    cached_via_numpy,
    cached_via_pickle,
    colorize,
)

warnings.filterwarnings('ignore', message=r'Accession .* found with incorrect name .*', category=UserWarning, module='pyimzml')


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


@async_threaded
def image_2d(filepath, mode, colormap=None, **kwargs):
    """
    Generates a 2D image from an .imz5 file.

    This function is intentionally not cached because it performs lightweight call-specific rendering options and output
    formatting. The expensive computation is delegated to ``image_2d_internal``, which is actually cached.

    Parameters
    ----------
    filepath: Path
        The path to the .imz5 file.
    mode: str
        Image generation mode.
    colormap: str, optional
        The colormap to use for colorization.
    **kwargs:
        Arguments that are to be handled by the ``image_2d_internal`` function.

    Returns
    -------
    image: str
        Base64-encoded PNG image.
    height: int
        Height of the image.
    width: int
        Width of the image.
    origin: tuple[int, int, int]
        Origin of the image.
    delta: tuple[int, int, int]
        Grid spacing of the image.
    colorbar: dict
        Plotly.js colorbar configuration.
    """
    image, height, width, origin, delta, must_colorize = image_2d_internal(filepath, mode=mode, **kwargs)
    image, colorbar = colorize(image, colormap or 'viridis') if must_colorize else (image, None)
    image = base64_png(image)
    return image, height, width, origin, delta, colorbar


@cached_via_pickle
def image_2d_internal(filepath, mode, **kwargs):
    with IMZ5(filepath) as file:
        depth, height, width = file.shape
        assert depth == 1, f'Expected a 2D image. Got {file.shape}'

        match mode:
            case 'tic':
                image = file.tic_image().squeeze()
                must_colorize = True
            case 'ion':
                image = file.ion_image(**kwargs).squeeze()
                must_colorize = True
            case 'pca':
                image = file.pca_image(**kwargs).squeeze()
                must_colorize = False
            case 'kmn':
                image = file.kmeans_image(**kwargs).squeeze() + 1
                must_colorize = True
            case other:
                raise NotImplementedError

        origin, delta = file.infer_grid()  # Assuming the grid is uniform.

    height, width, *channels = image.shape

    return image, height, width, origin, delta, must_colorize


@async_threaded
@cached_via_numpy
def spectrum_2d(filepath, x_min, x_max, y_min, y_max, precision):
    """
    Generates a spectrum from specified region in a .imz5 file.

    Parameters
    ----------
    filepath: Path
        The path to the .imz5 file.
    x_min, x_max, y_min, y_max: float
        Bounding box of the region.
    precision: float
        Binning precision.

    Returns
    -------
    locs: np.ndarray
        Mass-to-charge ratios.
    vals: np.ndarray
        TIC-normalized intensity values.
    """
    with IMZ5(filepath) as file:
        depth, height, width = file.shape
        assert depth == 1, f'Expected a 2D image. Got {file.shape}'
        return file.spectrum(x_min, x_max, y_min, y_max, precision=precision)
