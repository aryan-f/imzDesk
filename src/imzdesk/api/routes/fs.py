from pathlib import Path

import aiofiles
import aiofiles.os
from fastapi import APIRouter, Request, Query

from ..utils import raise_on_path

router = APIRouter()


@router.get('/list')
async def list(request: Request, path: str = Query('.')):
    root = request.app.state.root
    dirpath = root / Path(path.lstrip('/'))
    await raise_on_path(dirpath, root, dir_only=True)
    entries = await aiofiles.os.listdir(dirpath)
    return [
        {
            'name': name,
            'size': (await aiofiles.os.stat(dirpath / name)).st_size,
            'is_dir': await aiofiles.os.path.isdir(dirpath / name)
        }
        for name in entries if not name.startswith('.')
    ]


@router.get('/stat')
async def stat(request: Request, path: str = Query('.')):
    root = request.app.state.root
    target = root / Path(path.lstrip('/'))
    await raise_on_path(target, root)
    info = await aiofiles.os.stat(target)
    return {
        'name': target.name,
        'size': info.st_size,
        'is_dir': target.is_dir(),
        'is_file': target.is_file(),
        'modified_at': info.st_mtime,
        'path': target.relative_to(root).as_posix(),
    }
