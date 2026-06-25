from pathlib import Path

from fastapi import HTTPException

from imzdesk.io import CLASSES
from imzdesk.server.schema.filesystem import (
    FileType,
)


def resolve_path(workspace: Path, relpath: str, is_dir: bool = False, exists: bool = True):
    """
    Resolves a relative path to an absolute path.

    Parameters
    ----------
    workspace: Path
        The workspace directory.
    relpath: str
        Unsanitized relative path.
    is_dir: bool
        Path must be a directory.
    exists: bool
        Path must exist.

    Raises
    ------
    HTTPException(status_code=401)
        The path is outside the workspace.
    HTTPException(status_code=404)
        The path does not exist. This is only raised if ``exists`` is True.
    HTTPException(status_code=400)
        The path is not a directory. This is only raised if ``is_dir`` is True.

    Returns
    -------
    abspath: Path
        Resolved absolute path.
    """
    relpath = relpath.lstrip('/')
    relpath = Path(relpath)
    abspath = workspace / relpath
    resolved = abspath.resolve()

    if not resolved.is_relative_to(workspace):
        raise HTTPException(status_code=400, detail='The path is outside the workspace.')
    if exists and not resolved.exists():
        raise HTTPException(status_code=404, detail='The path does not exist.')
    if is_dir and not resolved.is_dir():
        raise HTTPException(status_code=400, detail='The path is not a directory.')

    return resolved


def resolve_filetype(abspath: Path) -> FileType | None:
    """
    Resolve the file type of ``abspath`` and return the corresponding IO class name.

    Parameters
    ----------
    abspath: Path
        The absolute path to the file.

    Returns
    -------
    FileType | None
        The name of the IO class, or None if the file type is not recognized.
    """
    for cls in CLASSES:
        if abspath.suffix in cls.extensions:
            return cls.__name__
    return None
