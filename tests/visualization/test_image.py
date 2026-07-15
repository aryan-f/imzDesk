from io import BytesIO

import numpy as np
from PIL import Image

from imzdesk.core import DImage
from imzdesk.visualization import DImageDisplay


def test_scalar_dimage_display_returns_rgb_pillow_image():
    image = DImage(
        values=np.array([0.0, 1.0, 2.0, 3.0]),
        coordinates=np.array([[0, 0], [1, 0], [0, 1], [1, 1]]),
    )

    rendered = DImageDisplay(image, colormap='viridis').image()

    assert isinstance(rendered, Image.Image)
    assert rendered.mode == 'RGB'
    assert rendered.size == (2, 2)


def test_multichannel_dimage_display_uses_first_three_channels():
    image = DImage(
        values=np.array([
            [0.0, 0.0, 0.0, 9.0],
            [1.0, 0.5, 0.25, 9.0],
        ]),
        coordinates=np.array([[0, 0], [1, 0]]),
    )

    rendered = DImageDisplay(image).image()

    assert rendered.size == (2, 1)


def test_display_save_writes_path_and_file_like_object(tmp_path):
    image = DImage(
        values=np.array([0.0, 1.0]),
        coordinates=np.array([[0, 0], [1, 0]]),
    )
    display = DImageDisplay(image)
    path = tmp_path / 'image.png'
    buffer = BytesIO()

    display.save(path)
    display.save(buffer, format='PNG')

    assert path.exists()
    assert buffer.getvalue().startswith(b'\x89PNG')


def test_display_plot_creates_axes_when_omitted():
    image = DImage(
        values=np.array([0.0, 1.0]),
        coordinates=np.array([[0, 0], [1, 0]]),
    )

    ax = DImageDisplay(image).plot()

    assert ax.images


def test_constant_scalar_image_scales_to_black():
    image = DImage(
        values=np.array([5.0, 5.0]),
        coordinates=np.array([[0, 0], [1, 0]]),
    )

    rendered = np.asarray(DImageDisplay(image).image())

    assert rendered.shape == (1, 2, 3)
