from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

import numpy as np
from PIL import Image
from matplotlib import colormaps
from matplotlib.axes import Axes

from imzdesk.core import DImage


class DImageDisplay:
    """
    Display a dense image.

    Parameters
    ----------
    image:
        Dense image to display.
    colormap:
        Matplotlib colormap name for scalar images.
    """

    def __init__(self, image: DImage, colormap: str = 'magma'):
        self.dimage = image
        self.colormap = colormap

    def plot(self, ax: Axes | None = None) -> Axes:
        """
        Draw the image on a matplotlib axes.

        Parameters
        ----------
        ax:
            Existing axes to draw on. A new axes is created when omitted.

        Returns
        -------
        matplotlib.axes.Axes
            Axes containing the rendered image.
        """
        if ax is None:
            import matplotlib.pyplot as plt
            _, ax = plt.subplots()
        ax.imshow(self._rgb())
        ax.set_axis_off()
        return ax

    def image(self) -> Image.Image:
        """
        Return a Pillow image.

        Returns
        -------
        PIL.Image.Image
            Rendered RGB image.
        """
        return Image.fromarray(self._uint8(), mode='RGB')

    def save(self, file: str | Path | BinaryIO, format: str | None = None) -> None:
        """
        Save the rendered image.

        Parameters
        ----------
        file:
            Filesystem path or file-like object.
        format:
            Optional Pillow output format. Useful for file-like objects.
        """
        self.image().save(file, format=format)

    def _grid(self) -> np.ndarray:
        values = np.asarray(self.dimage.values)
        coordinates = np.asarray(self.dimage.coordinates)[:, :2].astype(int)
        minimum_coordinates = coordinates.min(axis=0)
        maximum_coordinates = coordinates.max(axis=0)
        height = int(maximum_coordinates[1] - minimum_coordinates[1] + 1)
        width = int(maximum_coordinates[0] - minimum_coordinates[0] + 1)
        channels = 1 if values.ndim == 1 else values.shape[1]
        grid = np.zeros((height, width, channels), dtype=np.float32)
        x = coordinates[:, 0] - int(minimum_coordinates[0])
        y = coordinates[:, 1] - int(minimum_coordinates[1])
        if values.ndim == 1:
            grid[y, x, 0] = values
        else:
            grid[y, x, :] = values
        return grid[:, :, 0] if channels == 1 else grid

    def _rgb(self) -> np.ndarray:
        grid = self._grid()
        if grid.ndim == 2:
            return colormaps[self.colormap](self._scale_image(grid))[:, :, :3]
        return self._scale_channels(grid[:, :, :3])

    def _uint8(self) -> np.ndarray:
        return np.round(np.clip(self._rgb(), 0, 1) * 255).astype(np.uint8)

    @staticmethod
    def _scale_image(values: np.ndarray) -> np.ndarray:
        minimum = np.nanmin(values)
        maximum = np.nanmax(values)
        if maximum <= minimum:
            return np.zeros_like(values, dtype=np.float32)
        return (values - minimum) / (maximum - minimum)

    @staticmethod
    def _scale_channels(values: np.ndarray) -> np.ndarray:
        values = np.asarray(values, dtype=np.float32)
        flat = values.reshape(-1, values.shape[-1])
        minimums = np.nanmin(flat, axis=0)
        maximums = np.nanmax(flat, axis=0)
        ranges = np.where(maximums > minimums, maximums - minimums, 1)
        return ((flat - minimums) / ranges).reshape(values.shape)
