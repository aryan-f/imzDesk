import asyncio
import base64
import hashlib
import json
import pickle
from collections.abc import Callable, Coroutine
from concurrent.futures import ThreadPoolExecutor
from functools import partial, wraps
from io import BytesIO
from pathlib import Path
from typing import Any, ParamSpec, TypeVar

import aiofiles.os
import numpy as np
from PIL import Image
from fastapi import HTTPException
from matplotlib import colormaps


async def raise_on_path(path, *suffixes, root=None, dir_only=False):
    """
    Raises an exception if the path is not *valid*.

    Parameters
    ----------
    path: Path
        Path to be checked.
    suffixes: str, optional
        Allowed suffixes for path.
    root: Path, optional
        The root path to be checked against.
    dir_only: bool, optional
        Only accept directory paths.

    Raises
    ------
    HTTPException(403)
        If the path is outside the root directory. This is only raised if `root` is provided.
    HTTPException(404)
        If the path does not exist.
    HTTPException(400)
        If the path is not a directory. This is only raised if `dir_only` is set.
    HTTPException(405)
        If the path does have a while-listed suffix. This is only raised if `suffixes` are provided.
    """
    if root is not None:
        if not path.is_relative_to(root):
            raise HTTPException(status_code=403)
    if not await aiofiles.os.path.exists(path):
        raise HTTPException(status_code=404)
    if dir_only and (not await aiofiles.os.path.isdir(path)):
        raise HTTPException(status_code=400)
    if suffixes:
        if path.suffix not in suffixes:
            raise HTTPException(status_code=405)


def get_derived_file_path(owner, suffix, dirname='.imzDesk'):
    """
    Resolves the path to a *derived* file, corresponding to some `owner`.

    Parameters
    ----------
    owner: Path
        The path to the owner of the *derived* file.
    suffix: str
        Desired suffix for the file.
    dirname: str, optional
        Intermediate directory name.

    Returns
    -------
    Path
        The path where the *cache* file should be found.
    """
    cache_dir = (owner.parent / dirname) if dirname else owner.parent
    return cache_dir / owner.with_suffix(suffix).name


def get_cache_file_path(owner, uid, ext='', dirname=None, kwargs: dict = None):
    """
    Resolves the path to a *cache* file for derived data.

    Parameters
    ----------
    owner: Path
        The path to the owner of the *cache* file.
    uid: str
        Unique identifier for the derivation, e.g., function name.
    ext: str
        Extension of the *cache* file, e.g., ``"pickle"``.
    dirname: str, optional
        Name of the intermediate directory.
    kwargs: dict, optional
        Arbitrary keyword arguments, hashed to generate a unique identifier. Kwargs need to be JSON-serializable.

    Returns
    -------
    Path
        The path to the **cache** file.
    """
    key_data = json.dumps({key: value for key, value in kwargs.items()}) if isinstance(kwargs, dict) else ''
    key = hashlib.blake2b(key_data.encode('utf-8'), digest_size=16).hexdigest()
    return get_derived_file_path(owner, f".{uid}.{key}{ext}", dirname=dirname)


def get_metadata_path(owner, suffix='.meta.yaml'):
    """
    Returns the path to the metadata file for a given owner.

    Parameters
    ----------
    owner: Path
        The path to the owner of the metadata file.
    suffix: str
        Desired suffix for the file.

    Returns
    -------
    Path
        The path to where the metadata file should be found.
    """
    return owner.with_suffix(suffix)


P = ParamSpec("P")
R = TypeVar("R")


def async_threaded(func: Callable[P, R]) -> Callable[..., Coroutine[Any, Any, R]]:
    """
    Offloads ``func`` to a thread, returning an ``awaitable``.

    When wrapped function is being called, you may pass in a ``ThreadPoolExecutor`` as a keyword argument, ``executor``.
    In this case, the wrapped function will borrow a thread from the pool, rather than spawning a fresh one.

    Apply this decorator BEFORE ``cached_as_numpy_archive``.
    """

    @wraps(func)
    async def wrapper(*args: P.args, executor: ThreadPoolExecutor | None = None, **kwargs: P.kwargs) -> R:
        loop = asyncio.get_running_loop()
        call = partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, call)

    return wrapper


U = ParamSpec("U")
V = TypeVar("V")


def cached_via_pickle(func: Callable[U, V]) -> Callable[U, V]:
    """
    Caches the output of the wrapped function to a `.pickle` file.

    Wrapped function MUST have ``filepath: Path`` as its first and only positional argument. The wrapper will save the
    `pickle` file to ``filepath.parent``. Keyword arguments passed to the function are hashed to generate a ``key``,
    using which the decorator then names the `pickle` file as ``<func_name>.<key>.pickle``.

    Apply this decorator AFTER ``async_threaded``.
    """

    @wraps(func)
    def wrapper(filepath: Path, **kwargs: Any) -> V:
        cache_path = get_cache_file_path(filepath, uid=func.__name__, ext='.pickle', kwargs=kwargs)

        if cache_path.exists():
            with open(cache_path, 'rb') as file:
                return pickle.load(file)

        result = func(filepath, **kwargs)

        with open(cache_path, 'wb') as file:
            pickle.dump(result, file)

        return result

    return wrapper


def cached_via_numpy(func: Callable[U, V]) -> Callable[U, V]:
    """
    Caches the outputs of the wrapped function to a `.npz` file.

    Wrapped function MUST have ``filepath: Path`` as its first and only positional argument. The wrapper will save the
    `npz` file to ``filepath.parent``. Keyword arguments passed to the function are hashed to generate a ``key``, using
    which the decorator then names the `npz` file as ``<func_name>.<key>.npz``.

    Apply this decorator AFTER ``async_threaded``.
    """

    @wraps(func)
    def wrapper(filepath: Path, **kwargs: Any) -> V:
        cache_path = get_cache_file_path(filepath, uid=func.__name__, ext='.npz', kwargs=kwargs)

        if cache_path.exists():
            archive = np.load(cache_path)
            if len(archive.files) == 1:
                file, = archive.files
                return archive[file]
            return tuple(archive[f] for f in archive.files)

        result = func(filepath, **kwargs)

        result = result if isinstance(result, tuple) else [result]
        np.savez(cache_path, *result, allow_pickle=False)

        return result

    return wrapper


def colorize(image, colormap):
    """
    Colorizes an image using a colormap.

    Parameters
    ----------
    image: np.ndarray
        Input image shaped as ``(H, W)``.
    colormap: str
        Name of a ``matplotlib`` colormap.

    Returns
    -------
    np.ndarray
        Colorized image shaped as ``(H, W, 3)``, with values in [0, 1].
    """
    cmap = colormaps[colormap]

    discrete = np.issubdtype(image.dtype, np.integer)

    if discrete:
        values = np.unique(image)
        colored_values = np.arange(len(values), dtype=np.float32)
        color_image = np.zeros(image.shape, dtype=np.float32)
        for value, colored_value in zip(values, colored_values):
            color_image[image == value] = colored_value
        v_min = 0.0
        v_max = float(len(values) - 1)
        normalized = color_image / max(v_max, 1.0)
    else:
        v_min = float(image.min())
        v_max = float(image.max())
        normalized = (image - v_min) / (v_max - v_min + 1e-8)

    rgb = cmap(normalized)[..., :3].astype(np.float32)

    colorscale = [
        (float(sample), f"rgb({round(r * 255)}, {round(g * 255)}, {round(b * 255)})")
        for sample in np.linspace(0.0, 1.0, 256)
        for r, g, b, a in [cmap(sample)]
    ]

    colorbar = {
        "colorscale": colorscale,
        "cmin": v_min,
        "cmax": v_max,
    }

    if discrete:
        colorbar.update({
            "tickmode": "array",
            "tickvals": colored_values.tolist(),
            "ticktext": [str(value) for value in values.tolist()],
            "labels": values.tolist(),
        })

    return rgb, colorbar


def base64_png(image: np.ndarray):
    """
    Encodes an image represented as a numpy array into a base64-encoded PNG image.

    Parameters
    ----------
    image: np.ndarray
        Shaped (H, W, 3) with values in [0, 1].

    Returns
    -------
    str
        Base64-encoded PNG image.
    """
    image = (image * 255).astype(np.uint8)
    image = Image.fromarray(image)
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
