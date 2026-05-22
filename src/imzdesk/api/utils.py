import asyncio
import hashlib
import json
import os
import pickle
import tempfile
from collections.abc import Callable, Coroutine
from concurrent.futures import ThreadPoolExecutor
from functools import partial, wraps
from pathlib import Path
from typing import Any, ParamSpec, TypeVar

import aiofiles.os
from fastapi import HTTPException


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


def asynced(func: Callable[P, R]) -> Callable[..., Coroutine[Any, Any, R]]:
    """
    Offloads ``func`` to a thread, returning an ``awaitable``.

    When wrapped function is being called, you may pass in a ``ThreadPoolExecutor`` as a keyword argument, ``executor``.
    In this case, the wrapped function will borrow a thread from the pool, rather than spawning a fresh one.

    Apply this decorator BEFORE ``stashed``.
    """

    @wraps(func)
    async def wrapper(*args: P.args, executor: ThreadPoolExecutor | None = None, **kwargs: P.kwargs) -> R:
        loop = asyncio.get_running_loop()
        call = partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, call)

    return wrapper


U = ParamSpec("U")
V = TypeVar("V")


def stashed(func: Callable[U, V]) -> Callable[U, V]:
    """
    Caches the outputs of the wrapped function to a `pickle` file.

    Wrapped function MUST have ``filepath: Path`` as its first and only positional argument. The wrapper will save the
    `pickle` file to ``filepath.parent``.

    Keyword arguments passed to the function are hashed to generate a ``key``, using which the decorator then names the
    `pickle` file as ``<func_name>.<key>.pickle``.

    Apply this decorator AFTER ``asynced``.
    """

    @wraps(func)
    def wrapper(filepath: Path, **kwargs: Any) -> V:
        key_data = json.dumps({key: json_or_none(value) for key, value in kwargs.items()})
        key = hashlib.blake2b(key_data.encode('utf-8'), digest_size=16).hexdigest()
        cache_path = get_derived_file_path(filepath, f".{func.__name__}.{key}.pickle", dirname=None)

        if cache_path.exists():
            with cache_path.open("rb") as file:
                return pickle.load(file)

        result = func(filepath, **kwargs)

        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=filepath.parent,
            prefix=f".{func.__name__}.{key}.",
            suffix=".tmp",
            delete=False,
        ) as file:
            temp_path = Path(file.name)
            pickle.dump(result, file, protocol=pickle.HIGHEST_PROTOCOL)

        os.replace(temp_path, cache_path)

        return result

    return wrapper


def json_or_none(obj: Any) -> str | None:
    try:
        return json.dumps(obj)
    except TypeError:
        return None
