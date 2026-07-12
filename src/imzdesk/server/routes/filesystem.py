import asyncio
import logging
import stat
from typing import List

import aiofiles.os
from fastapi import APIRouter, Request

from imzdesk.server.schema import filesystem
from imzdesk.server.utils.filesystem import resolve_path, resolve_filetype

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get('/listdir')
async def listdir(request: Request, dirpath: str) -> List[filesystem.FilesystemEntry]:
    workspace = request.app.state.settings.workspace

    directory = await resolve_path(workspace, dirpath, is_dir=True)
    paths = [directory / name for name in await aiofiles.os.listdir(directory) if not name.startswith('.')]
    stats = await asyncio.gather(*(aiofiles.os.stat(path) for path in paths))
    entries = sorted(zip(paths, stats),
        key=lambda entry: (not stat.S_ISDIR(entry[1].st_mode), entry[0].name.lower()),
    )

    return [
        filesystem.FilesystemEntry(
            name=path.name,
            path=str(path.relative_to(workspace)),
            directory=stat.S_ISDIR(info.st_mode),
            parent=str(path.parent.relative_to(workspace)),
            size=info.st_size if stat.S_ISREG(info.st_mode) else None,
            type=resolve_filetype(path),
        )
        for path, info in entries
    ]
