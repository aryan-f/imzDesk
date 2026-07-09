import numpy as np
from scipy import sparse


class RImage:

    def __init__(self, coordinates, positions, values, offsets):
        """
        Ragged image.

        Parameters
        ----------
        coordinates: np.ndarray
            Pixel coordinates for each row of data.
        positions: np.ndarray
            Concatenated channel positions for ragged pixel data.
        values: np.ndarray
            Concatenated sparse values for ragged pixel data.
        offsets: np.ndarray
            Start offsets for each pixel in ``positions`` and ``values``.
        """
        self.coordinates = np.asarray(coordinates)
        self.positions = np.asarray(positions)
        self.values = np.asarray(values)
        self.offsets = np.asarray(offsets)

    def __len__(self):
        return self.coordinates.shape[0]

    def pixel(self, index: int) -> tuple[np.ndarray, np.ndarray]:
        start = self.offsets[index]
        stop = self.offsets[index + 1]
        return self.positions[start:stop], self.values[start:stop]


class SImage:

    def __init__(self, values, coordinates):
        """
        Sparse image.

        Parameters
        ----------
        values: sparse.spmatrix
            Sparse matrix with one row per pixel.
        coordinates: np.ndarray
            Pixel coordinates matching rows of ``values``.
        """
        self.values = values
        self.coordinates = np.asarray(coordinates)

    def __len__(self):
        return self.coordinates.shape[0]


class DImage:

    def __init__(self, values, coordinates):
        """
        Dense image.

        Parameters
        ----------
        values: np.ndarray
            Dense matrix with one row per pixel.
        coordinates: np.ndarray
            Pixel coordinates matching rows of ``values``.
        """
        self.values = np.asarray(values)
        self.coordinates = np.asarray(coordinates)
