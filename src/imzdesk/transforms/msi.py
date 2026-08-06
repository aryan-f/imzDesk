import numpy as np

from imzdesk.core import RImage, DImage
from imzdesk.io import MSI
from imzdesk.transforms.base import Transform
from imzdesk.transforms.models import MODELS


class ToRImage(Transform):
    """
    Read an MSI into an in-memory ragged image.

    Notes
    -----
    This transform reads directly from the ``.ibd`` file using offsets already
    parsed by pyimzML.
    """

    def __call__(self, image: MSI) -> RImage:
        coordinates = self._spatial_coordinates(image)
        lengths = np.asarray(image.reader.mzLengths, dtype=np.int64)
        intensity_lengths = np.asarray(image.reader.intensityLengths, dtype=np.int64)
        pixel_offsets = np.concatenate([[0], np.cumsum(lengths)])
        mz = np.empty(pixel_offsets[-1], dtype=np.float64)
        intensities = np.empty(pixel_offsets[-1], dtype=np.float32)
        ibd_bytes = np.memmap(image.ibd_path, mode='r')
        mz_dtype = np.dtype(image.reader.mzPrecision)
        intensity_dtype = np.dtype(image.reader.intensityPrecision)
        for spectrum_index in range(len(image)):
            pixel_start = pixel_offsets[spectrum_index]
            pixel_stop = pixel_offsets[spectrum_index + 1]
            mz[pixel_start:pixel_stop] = np.frombuffer(
                ibd_bytes,
                dtype=mz_dtype,
                count=lengths[spectrum_index],
                offset=image.reader.mzOffsets[spectrum_index],
            )
            intensities[pixel_start:pixel_stop] = np.frombuffer(
                ibd_bytes,
                dtype=intensity_dtype,
                count=intensity_lengths[spectrum_index],
                offset=image.reader.intensityOffsets[spectrum_index],
            )
        return RImage(
            coordinates=coordinates,
            positions=mz,
            values=intensities,
            offsets=pixel_offsets,
        )

    @staticmethod
    def _spatial_coordinates(image: MSI) -> np.ndarray:
        coordinates = np.asarray(image.coordinates)
        if coordinates.ndim != 2:
            raise ValueError('MSI coordinates must be a 2D array.')
        if coordinates.shape[1] == 2:
            return coordinates.copy()
        if coordinates.shape[1] != 3:
            raise ValueError('MSI coordinates must have shape (n_pixels, 2) or (n_pixels, 3).')
        z = coordinates[:, 2]
        if not np.all(z == z[0]):
            raise ValueError('3D MSI coordinates are not supported; z must be constant.')
        return coordinates[:, :2].copy()


class Embed(Transform):

    def __init__(self, model: str = '', batch_size: int = 128):
        """
        Embed ragged image data with an external model.

        Parameters
        ----------
        model: str
            Model identifier.
        batch_size: int
            Number of spectra embedded in each inference batch.
        """
        if not isinstance(batch_size, int) or isinstance(batch_size, bool) or batch_size < 1:
            raise ValueError('batch_size must be a positive integer.')
        assert model in MODELS, f'Unknown model: {model}'
        constructor = MODELS[model]
        self.model = constructor()
        self.batch_size = batch_size

    def __call__(self, image: RImage) -> DImage:
        return self.model.embed(image, batch_size=self.batch_size)
