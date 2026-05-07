import asyncio
import hashlib
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


def get_cached_path(owner, suffix):
    """
    Resolves the path to a *cache* file, corresponding to some `owner`.

    Parameters
    ----------
    owner: Path
        The path to the owner of the *cache* file.
    suffix: str
        Desired suffix for the file.

    Returns
    -------
    Path
        The path where the *cache* file should be found.
    """
    cache_dir = owner.parent / '.imzDesk'
    return cache_dir / owner.with_suffix(suffix).name


P = ParamSpec("P")
R = TypeVar("R")


def asynced(func: Callable[P, R]) -> Callable[..., Coroutine[Any, Any, R]]:

    @wraps(func)
    async def wrapper(*args: P.args, executor: ThreadPoolExecutor | None = None, **kwargs: P.kwargs) -> R:
        loop = asyncio.get_running_loop()
        call = partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, call)

    return wrapper


U = ParamSpec("U")
V = TypeVar("V")


def stashed(func: Callable[U, V]) -> Callable[U, V]:

    @wraps(func)
    def wrapper(filepath: Path, **kwargs: Any) -> V:
        key_data = pickle.dumps(
            tuple(sorted(kwargs.items(), key=lambda item: item[0])),
            protocol=pickle.HIGHEST_PROTOCOL,
        )

        key = hashlib.blake2b(key_data, digest_size=16).hexdigest()
        cache_path = filepath.parent / f"{func.__name__}.{key}.pickle"

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
