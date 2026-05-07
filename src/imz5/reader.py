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


