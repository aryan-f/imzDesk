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

    @property
    def coordinates(self):
        return self.file[A.COORDINATES]

    @property
    def shape(self):
        x = self.coordinates[:, 0]
        y = self.coordinates[:, 1]
        z = self.coordinates[:, 2]

        height = int(y.max() - y.min()) + 1
        width = int(x.max() - x.min()) + 1
        depth = int(z.max() - z.min()) + 1

        return (height, width, depth) if depth > 1 else (height, width)

    @property
    def ndim(self):
        return len(self.shape)

    def __getitem__(self, key):
        pass  # TODO

    def spectrum(
        self,
        x_min: float = -np.inf,
        x_max: float = np.inf,
        y_min: float = -np.inf,
        y_max: float = np.inf,
        bin_width: float = 1.0,
        dtype=np.float32,
    ):
        if bin_width <= 0:
            return np.array([], dtype=np.float64), np.array([], dtype=dtype)

        coordinates = self.file[A.COORDINATES][:]
        offsets = self.file[A.OFFSETS][:]

        x = coordinates[:, 0]
        y = coordinates[:, 1]

        pixel_mask = (
                (x >= x_min) &
                (x < x_max) &
                (y >= y_min) &
                (y < y_max)
        )

        pixel_ids = np.flatnonzero(pixel_mask)

        if len(pixel_ids) == 0:
            return np.array([], dtype=np.float64), np.array([], dtype=dtype)

        locations_dataset = self.file[A.LOCATIONS]
        values_dataset = self.file[A.VALUES]

        intensity = np.zeros(0, dtype=dtype)

        # Group consecutive pixel IDs so HDF5 reads larger contiguous point slices
        # instead of thousands of tiny per-pixel slices.
        breaks = np.flatnonzero(np.diff(pixel_ids) != 1) + 1
        run_starts = np.r_[0, breaks]
        run_ends = np.r_[breaks, len(pixel_ids)]

        for run_start, run_end in zip(run_starts, run_ends):
            first_pixel = pixel_ids[run_start]
            last_pixel = pixel_ids[run_end - 1]

            point_start = int(offsets[first_pixel])
            point_end = int(offsets[last_pixel + 1])

            if point_end <= point_start:
                continue

            locations = locations_dataset[point_start:point_end]
            values = values_dataset[point_start:point_end].astype(dtype, copy=False)

            if len(locations) == 0:
                continue

            bin_ids = (locations / bin_width).astype(np.int64)

            # m/z should not be negative, but this keeps the endpoint sane.
            valid = bin_ids >= 0
            bin_ids = bin_ids[valid]
            values = values[valid]

            if len(bin_ids) == 0:
                continue

            binned = np.bincount(bin_ids, weights=values).astype(dtype, copy=False)

            if len(binned) > len(intensity):
                expanded = np.zeros(len(binned), dtype=dtype)
                expanded[:len(intensity)] = intensity
                intensity = expanded

            intensity[:len(binned)] += binned

        if len(intensity) == 0:
            return np.array([], dtype=np.float64), np.array([], dtype=dtype)

        nonzero = intensity > 0

        if not nonzero.any():
            return np.array([], dtype=np.float64), np.array([], dtype=dtype)

        intensity = intensity[nonzero]

        bin_ids = np.flatnonzero(nonzero)
        mz = (bin_ids.astype(np.float64) + 0.5) * bin_width

        base_peak = intensity.max()

        if base_peak > 0:
            intensity = intensity / base_peak

        return mz, intensity

    def tic(self, fill_value=0, dtype=np.float32):
        """
        Computes the total ion current image.

        Parameters
        ----------
        fill_value: float, default=0
            Value used for missing pixel positions.
        dtype: numpy dtype, default=np.float32
            Output tensor data type.

        Returns
        -------
        image: numpy.ndarray
            TIC output as either `(height, width)` for 2D MSI data, or `(height, width, depth)` for 3D MSI data.
        """
        coordinates = self.file[A.COORDINATES][:]
        offsets = self.file[A.OFFSETS][:]
        values = self.file[A.VALUES][:].astype(dtype, copy=False)

        lengths = np.diff(offsets)
        nonempty = lengths > 0

        pixel_tic = np.zeros(len(coordinates), dtype=dtype)

        if nonempty.any():
            pixel_tic[nonempty] = np.add.reduceat(values, offsets[:-1][nonempty])

        x = coordinates[:, 0]
        y = coordinates[:, 1]
        z = coordinates[:, 2]

        x_min = x.min()
        y_min = y.min()
        z_min = z.min()

        image = np.full(self.shape, fill_value, dtype=dtype)

        if image.ndim == 3:
            image[y - y_min, x - x_min, z - z_min] = pixel_tic
        else:
            image[y - y_min, x - x_min] = pixel_tic

        return image


