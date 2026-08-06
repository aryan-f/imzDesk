import numpy as np
from PIL import Image
from matplotlib import colormaps


class DImageDisplay:

    def __init__(self, image, colormap='magma'):
        """
        Initialize a dense-image display.

        Parameters
        ----------
        image : imzdesk.core.DImage
            Dense image to display.
        colormap : str, default='magma'
            Matplotlib colormap name for scalar images.

        Attributes
        ----------
        dimage : imzdesk.core.DImage
            Dense image to display.
        """
        self.dimage = image
        self.colormap = colormap

    def plot(self, ax=None):
        """
        Draw the image on a matplotlib axes.

        Parameters
        ----------
        ax : matplotlib.axes.Axes, optional
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

    def image(self):
        """
        Return a Pillow image.

        Returns
        -------
        PIL.Image.Image
            Rendered RGB image.
        """
        return Image.fromarray(self._uint8(), mode='RGB')

    def save(self, file, format=None):
        """
        Save the rendered image.

        Parameters
        ----------
        file : str, pathlib.Path, or binary file-like object
            Filesystem path or file-like object.
        format : str, optional
            Optional Pillow output format. Useful for file-like objects.
        """
        self.image().save(file, format=format)

    def _grid(self):
        """
        Place measured dense values on their spatial grid.

        Returns
        -------
        numpy.ndarray
            Scalar or multichannel spatial grid.
        """
        values = np.asarray(self.dimage.values)
        coordinates = np.asarray(self.dimage.coordinates).astype(int)
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

    def _rgb(self):
        """
        Convert the dense value grid to normalized RGB values.

        Returns
        -------
        numpy.ndarray
            Floating-point RGB image in the unit interval.
        """
        grid = self._grid()
        if grid.ndim == 2:
            return colormaps[self.colormap](self._scale_image(grid))[:, :, :3]
        return self._scale_channels(grid[:, :, :3])

    def _uint8(self):
        """
        Convert normalized RGB values to unsigned 8-bit values.

        Returns
        -------
        numpy.ndarray
            Unsigned 8-bit RGB image.
        """
        return np.round(np.clip(self._rgb(), 0, 1) * 255).astype(np.uint8)

    @staticmethod
    def _scale_image(values):
        """
        Scale a scalar image to the unit interval.

        Parameters
        ----------
        values : numpy.ndarray
            Scalar image values.

        Returns
        -------
        numpy.ndarray
            Scaled image values.
        """
        minimum = np.nanmin(values)
        maximum = np.nanmax(values)
        if maximum <= minimum:
            return np.zeros_like(values, dtype=np.float32)
        return (values - minimum) / (maximum - minimum)

    @staticmethod
    def _scale_channels(values):
        """
        Scale each image channel independently to the unit interval.

        Parameters
        ----------
        values : numpy.ndarray
            Channel-last image values.

        Returns
        -------
        numpy.ndarray
            Independently scaled channels.
        """
        values = np.asarray(values, dtype=np.float32)
        flat = values.reshape(-1, values.shape[-1])
        minimums = np.nanmin(flat, axis=0)
        maximums = np.nanmax(flat, axis=0)
        ranges = np.where(maximums > minimums, maximums - minimums, 1)
        return ((flat - minimums) / ranges).reshape(values.shape)
