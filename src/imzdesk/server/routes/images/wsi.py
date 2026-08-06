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


def cache_info(function):
    info = getattr(function, 'cache_info', None)
    return info() if info is not None else '<unavailable>'


# Keep an LRU cache for consecutive file access.
@functools.lru_cache(maxsize=4)
def get_wsi_instance(filepath: pathlib.Path | str):
    logger.debug('Creating cached WSI reader path=%s', filepath)
    return WSI(filepath)


@router.get('/tile')
async def tile(request: Request, filepath: str, level: int, row: int, column: int):
    workspace = request.app.state.settings.workspace
    logger.debug('WSI tile requested filepath=%s level=%d row=%d column=%d', filepath, level, row, column)
    filepath = await resolve_path(workspace, filepath)
    return await tile_impl(request, filepath, level, row, column)


@threaded
def tile_impl(filepath: pathlib.Path, level: int, row: int, column: int):
    wsi = get_wsi_instance(filepath)
    logger.debug('Using WSI reader path=%s cache=%s', filepath, cache_info(get_wsi_instance))
    im = wsi.get_tile(level, row, column)
    buffer = io.BytesIO()
    im.save(buffer, format='PNG')
    payload = buffer.getvalue()
    logger.debug(
        'Rendered WSI tile path=%s level=%d row=%d column=%d size=%s bytes=%d',
        filepath,
        level,
        row,
        column,
        im.size,
        len(payload),
    )
    return Response(
        payload,
        media_type='image/png',
        headers={
            'Cache-Control': 'public, max-age=31536000, immutable',
        },
    )
