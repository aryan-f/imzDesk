import logging
from typing import List

from fastapi import APIRouter, Request

from imzdesk.server.schema import filesystem
from imzdesk.server.utils.filesystem import resolve_path, resolve_filetype

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get('/listdir')
def listdir(request: Request, dirpath: str) -> List[filesystem.FilesystemEntry]:
    workspace = request.app.state.settings.workspace

    directory = resolve_path(workspace, dirpath, is_dir=True)

    # Sort alphabetically, directories at the top.
    entries = sorted(
        directory.iterdir(),
        key=lambda path: (not path.is_dir(), path.name.lower()),
    )

    return [
        filesystem.FilesystemEntry(
            directory=entry.is_dir(),
            parent=str(entry.parent.relative_to(workspace)),
            name=entry.name,
            path=str(entry.relative_to(workspace)),
            size=entry.stat().st_size if entry.is_file() else None,
            type=resolve_filetype(entry),
        )
        for entry in entries if not entry.stem.startswith('.')
    ]
