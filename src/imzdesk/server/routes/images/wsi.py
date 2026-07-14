import functools
import io
import logging
import pathlib

from fastapi import APIRouter, Request
from fastapi.responses import Response

from imzdesk.io import WSI
from imzdesk.server.utils.executor import threaded
from imzdesk.server.utils.filesystem import resolve_path

router = APIRouter()
logger = logging.getLogger(__name__)


# Keep an LRU cache for consecutive file access.
@functools.lru_cache(maxsize=4)
def get_wsi_instance(filepath: pathlib.Path | str):
    return WSI(filepath)


@router.get('/metadata')
async def metadata(request: Request, filepath: str) -> WSI.metadata_class:
    workspace = request.app.state.settings.workspace
    filepath = await resolve_path(workspace, filepath)
    return await metadata_impl(request, filepath)


@threaded
def metadata_impl(filepath: pathlib.Path):
    return WSI.read_metadata(filepath)


@router.get('/tile')
async def tile(request: Request, filepath: str, level: int, row: int, column: int):
    workspace = request.app.state.settings.workspace
    filepath = await resolve_path(workspace, filepath)
    return await tile_impl(request, filepath, level, row, column)


@threaded
def tile_impl(filepath: pathlib.Path, level: int, row: int, column: int):
    wsi = get_wsi_instance(filepath)
    im = wsi.get_tile(level, row, column)
    buffer = io.BytesIO()
    im.save(buffer, format='PNG')
    return Response(
        buffer.getvalue(),
        media_type='image/png',
        headers={
            'Cache-Control': 'public, max-age=31536000, immutable',
        },
    )
