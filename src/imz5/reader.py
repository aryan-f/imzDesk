from functools import cached_property

import h5py
import numpy as np

from .schema import A


class IMZ5:

    def __init__(self, filepath):
        """
        Reader class for `.imz5` files.

        Parameters
        ----------
        filepath: str or pathlib.Path
            The path to the `.imz5` file.
        """
        self.file = h5py.File(filepath, 'r')

    def close(self):
        """Closes the underlying HDF5 file."""
        self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    @property
    def coordinates(self) -> h5py.Dataset:
        """
        Pixel coordinates as a `(N, 3)` array of `[x, y, z]` integers, one row per pixel, in the original acquisition
        order.
        """
        return self.file[A.COORDINATES]

    @property
    def offsets(self) -> h5py.Dataset:
        """
        Cumulative spectral offsets as a `(N+1)` ``int64`` array, where `N` is the number of pixels. For pixel ``i``,
        its spectral data spans ``offsets[i]:offsets[i+1]``, in ``locations``, ``values``, and ``ids``.
        ``offsets[0]`` is always 0 and ``offsets[-1]`` is the total number of spectral points.
        """
        return self.file[A.OFFSETS]

    @property
    def locations(self) -> h5py.Dataset:
        """
        m/z locations of all spectral points across all pixels, as a flat `(M)` ``float64`` array, where `M` is the
        total number of spectral points. Not sorted by pixel; use ``offsets`` to slice per-pixel ranges.
        """
        return self.file[A.LOCATIONS]

    @property
    def values(self) -> h5py.Dataset:
        """
        Intensity values corresponding to each entry in locations, as a flat `(M)` ``float32`` array.
        """
        return self.file[A.VALUES]

    @property
    def ids(self) -> h5py.Dataset:
        """
        Pixel index for each spectral point, as a flat `(M)` ``int64`` array. ``ids[k]`` is the index into coordinates
        of the pixel that owns the `k`-th spectral point. Redundant with ``offsets`` but enables direct weighted
        aggregation via ``np.bincount``.
        """
        return self.file[A.IDS]

    @cached_property
    def bounds(self) -> tuple[float, float, float, float, float, float]:
        """
        Boundaries of the acquisition in the original coordinate space, returned as
        ``(x_min, y_min, z_min, x_max, y_max, z_max)``.
        """
        coords = self.coordinates[:]
        x, y, z = coords[:, 0], coords[:, 1], coords[:, 2]
        return x.min(), y.min(), z.min(), x.max(), y.max(), z.max()

    @property
    def shape(self) -> tuple[int, int, int]:
        """
        Spatial extent of the dataset as (D, H, W), derived from the ``coordinates``. Always 3D regardless of whether
        the acquisition is 2D (in which case ``D=1``).
        """
        x_min, y_min, z_min, x_max, y_max, z_max = self.bounds
        return (
            int(z_max - z_min) + 1,
            int(y_max - y_min) + 1,
            int(x_max - x_min) + 1,
        )

    def scatter(self, per_pixel):
        """
        Scatters per-pixel values into a spatial image array using the stored coordinates.

        Pixel ``i`` is placed at the voxel corresponding to its `(x, y, z)` coordinate, offset by the coordinate
        minimums so the output is zero-indexed. Unvisited voxels (pixels absent from the acquisition) are left as zero.

        Parameters
        ----------
        per_pixel: np.ndarray
            Values indexed by pixel acquisition order. A 1D input produces a scalar-per-voxel image; a 2D input
            produces a vector-per-voxel image.

        Returns
        -------
        np.ndarray
            shaped (D, H, W) or (D, H, W, C).
        """
        coords = self.coordinates[:]
        x, y, z = coords[:, 0], coords[:, 1], coords[:, 2]
        x_min, y_min, z_min, x_max, y_max, z_max = self.bounds
        D, H, W = self.shape

        out_shape = (D, H, W) if per_pixel.ndim == 1 else (D, H, W, per_pixel.shape[1])
        image = np.zeros(out_shape, dtype=per_pixel.dtype)
        image[
            (z - z_min).astype(int),
            (y - y_min).astype(int),
            (x - x_min).astype(int),
        ] = per_pixel

        return image

    def binned(self, bin_width=1, normalization='tic'):
        """
        Bins all the spectra onto a common m/z grid and optionally normalizes.

        Parameters
        ----------
        bin_width : float
            Width of each m/z bin in Daltons. Default is 1.
        normalization : str or None
            ``'tic'`` divides each pixel spectrum by its total ion count.
            ``'rms'`` divides by its root-mean-square.
            ``None`` skips normalization.

        Returns
        -------
        matrix: np.ndarray
            Binned spectra, shaped as `(N, n_bins)`.
        bins: np.ndarray
            Bin edges in m/z space, shaped as a flat `(n_bins + 1)` vector.
        """
        locs = self.locations[:]
        vals = self.values[:]
        ids = self.ids[:]
        num_pixels = len(self.offsets) - 1

        mz_min, mz_max = locs.min(), locs.max()
        bins = np.arange(mz_min, mz_max + bin_width, bin_width)
        n_bins = len(bins) - 1

        bin_idx = np.clip(np.searchsorted(bins, locs, side='right') - 1, 0, n_bins - 1)

        matrix = np.zeros((num_pixels, n_bins), dtype=np.float32)
        np.add.at(matrix, (ids, bin_idx), vals)

        if normalization == 'tic':
            tic = matrix.sum(axis=1, keepdims=True)
            tic[tic == 0] = 1
            matrix /= tic
        elif normalization == 'rms':
            rms = np.sqrt((matrix ** 2).mean(axis=1, keepdims=True))
            rms[rms == 0] = 1
            matrix /= rms

        return matrix, bins

    def mask_ion(self, mz, tolerance=0.01):
        """
        Returns the indices (into ``locations``/``values``/``ids``) of all spectral points whose m/z falls within
        `[mz - tolerance / 2, mz + tolerance / 2]`.

        Parameters
        ----------
        mz: float
            Target m/z value.
        tolerance: float
            m/z value tolerance. Default 0.01.

        Returns
        -------
        np.ndarray
            Indices into the flat spectral arrays.
        """
        half = tolerance / 2
        lo, hi = mz - half, mz + half
        locations = self.locations[:]
        return np.flatnonzero((locations >= lo) & (locations <= hi))

    def spectrum(self, x_min=-np.inf, x_max=np.inf, y_min=-np.inf, y_max=np.inf, z_min=-np.inf, z_max=np.inf, precision=0.001):
        """
        Returns the TIC-normalized summed spectrum for a spatial region as a
        (locations, values) tuple of 1D arrays sorted by m/z.

        Parameters
        ----------
        x_min, x_max, y_min, y_max, z_min, z_max: float
            Inclusive coordinate bounds. Default to -inf/inf (entire image).
        precision: float
            m/z values are rounded to this interval before aggregation,
            collapsing near-duplicate peaks. Default 0.001.

        Returns
        -------
        locations: np.ndarray
            Mass-to-charge ratios.
        values: np.ndarray
            Intensity values.
        """
        coords = self.coordinates[:]
        x, y, z = coords[:, 0], coords[:, 1], coords[:, 2]
        pixel_mask = (
            (x >= x_min) & (x <= x_max) &
            (y >= y_min) & (y <= y_max) &
            (z >= z_min) & (z <= z_max)
        )

        ids = self.ids[:]
        point_mask = pixel_mask[ids]

        if not point_mask.any():
            return np.array([], dtype=np.float64), np.array([], dtype=np.float32)

        locations = self.locations[:]
        values = self.values[:]

        locs = np.round(locations[point_mask] / precision) * precision
        vals = values[point_mask]

        unique_locs, inverse = np.unique(locs, return_inverse=True)
        unique_vals = np.zeros(len(unique_locs), dtype=np.float32)
        np.add.at(unique_vals, inverse, vals)

        tic = unique_vals.sum()
        if tic > 0:
            unique_vals /= tic

        return unique_locs, unique_vals
