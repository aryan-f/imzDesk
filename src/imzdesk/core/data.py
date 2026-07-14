import numpy as np
from scipy import sparse


class RImage:

    def __init__(self, coordinates, positions, values, offsets):
        """
        Ragged image data.

        An ``RImage`` stores one variable-length feature vector per pixel. It is
        the current representation for raw profile/centroid spectra before they
        are converted into a rectangular feature matrix.

        Parameters
        ----------
        coordinates: np.ndarray
            Pixel coordinates. Shape is ``(n_pixels, 2)``.
        positions: np.ndarray
            Concatenated feature/channel positions. Shape is ``(n_values,)``.
        values: np.ndarray
            Concatenated sparse values. Shape is ``(n_values,)``.
        offsets: np.ndarray
            Segment boundaries into ``positions`` and ``values``. Shape is
            ``(n_pixels + 1,)``.

        Attributes
        ----------
        coordinates: np.ndarray
            Spatial ``x``/``y`` pixel coordinates with shape ``(n_pixels, 2)``.
        positions: np.ndarray
            Concatenated feature/channel positions with shape ``(n_values,)``.
            For MSI this is m/z.
        values: np.ndarray
            Concatenated sparse values with shape ``(n_values,)``. Entry ``j``
            is aligned with ``positions[j]``.
        offsets: np.ndarray
            Segment boundaries with shape ``(n_pixels + 1,)``. Pixel ``i``
            occupies ``positions[offsets[i]:offsets[i + 1]]`` and
            ``values[offsets[i]:offsets[i + 1]]``.
        """
        self.coordinates = np.asarray(coordinates)
        self.positions = np.asarray(positions)
        self.values = np.asarray(values)
        self.offsets = np.asarray(offsets)

    def __len__(self):
        n_pixels, n_dims = self.coordinates.shape
        return n_pixels

    def pixel(self, index: int) -> tuple[np.ndarray, np.ndarray]:
        """
        Return one pixel's ragged feature positions and values.

        Parameters
        ----------
        index: int
            Pixel row index.

        Returns
        -------
        positions: np.ndarray
            Feature/channel positions for the selected pixel.
        values: np.ndarray
            Values aligned with ``positions`` for the selected pixel.
        """
        start = self.offsets[index]
        stop = self.offsets[index + 1]
        return self.positions[start:stop], self.values[start:stop]


class SImage:
    def __init__(self, values, coordinates):
        """
        Sparse rectangular image data.

        An ``SImage`` stores one fixed-length sparse feature vector per pixel.
        It is the current representation after ragged data has been converted
        into a shared feature/channel basis, for example by binning m/z values.

        Parameters
        ----------
        values: sparse.spmatrix
            Sparse matrix with shape ``(n_pixels, n_features)``.
        coordinates: np.ndarray
            Pixel coordinates matching rows of ``values``. Shape is
            ``(n_pixels, 2)``.

        Attributes
        ----------
        values: sparse.spmatrix
            Sparse matrix with shape ``(n_pixels, n_features)``. Row ``i`` is
            the fixed-length feature vector for pixel ``i``.
        coordinates: np.ndarray
            Spatial ``x``/``y`` pixel coordinates with shape ``(n_pixels, 2)``.
            Row ``i`` describes the same pixel as row ``i`` of ``values``.
        """
        self.values = values
        self.coordinates = np.asarray(coordinates)

    def __len__(self):
        n_pixels, n_dims = self.coordinates.shape
        return n_pixels


class DImage:
    def __init__(self, values, coordinates):
        """
        Dense rectangular image data.

        A ``DImage`` stores one fixed-length dense feature vector per pixel. It
        is the current representation used by reducers that require dense input
        and by visualization code that renders one or more dense channels back
        onto the image grid.

        Parameters
        ----------
        values: np.ndarray
            Dense values. Shape is ``(n_pixels,)`` or
            ``(n_pixels, n_features)``.
        coordinates: np.ndarray
            Pixel coordinates matching rows of ``values``. Shape is
            ``(n_pixels, 2)``.

        Attributes
        ----------
        values: np.ndarray
            Dense values with shape ``(n_pixels,)`` for scalar images or
            ``(n_pixels, n_features)`` for multichannel images. Row ``i`` is
            the dense feature vector for pixel ``i``.
        coordinates: np.ndarray
            Spatial ``x``/``y`` pixel coordinates with shape ``(n_pixels, 2)``.
            Row ``i`` describes the same pixel as row ``i`` of ``values``.
        """
        self.values = np.asarray(values)
        self.coordinates = np.asarray(coordinates)

    def to_image(self, target_mpp: float | tuple[float, float] | None = None, shape: tuple[int, int] | None = None, crop: bool = True):
        """
        Rasterize dense pixel values into a numpy image.

        Parameters
        ----------
        target_mpp:
            Accepted for API symmetry with image file classes.
        shape:
            Optional ``(height, width)`` output shape.
        crop:
            Accepted for API symmetry with image file classes.

        Returns
        -------
        image: np.ndarray
            Rasterized image with shape ``(height, width)`` or
            ``(height, width, channels)``.
        """
        coordinates = self.coordinates.astype(np.int64)
        height, width = shape or (coordinates[:, 1].max() + 1, coordinates[:, 0].max() + 1)
        if self.values.ndim == 1:
            image = np.zeros((height, width), dtype=self.values.dtype)
            image[coordinates[:, 1], coordinates[:, 0]] = self.values
            return image
        image = np.zeros((height, width, self.values.shape[1]), dtype=self.values.dtype)
        image[coordinates[:, 1], coordinates[:, 0]] = self.values
        return image
