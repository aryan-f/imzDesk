from pathlib import Path

import aiofiles.os
from fastapi import HTTPException


async def raise_on_path(path, root=None, *suffixes, dir_only=False):
    """
    Raises an exception if the path is not *valid*.

    Parameters
    ----------
    path: Path
        Path to be checked.
    root: Path, optional
        The root path to be checked against.
    suffixes: str, optional
        Allowed suffixes for path.
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
