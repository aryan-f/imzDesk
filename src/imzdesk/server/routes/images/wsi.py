import functools
import io
import logging
import pathlib

from fastapi import APIRouter, Request
from fastapi.responses import Response

from imzdesk.io import WSI
from imzdesk.server.utils.filesystem import resolve_path

router = APIRouter()
logger = logging.getLogger(__name__)


# Keep an LRU cache for consecutive file access.
@functools.lru_cache(maxsize=8)
def get_wsi_instance(filepath: pathlib.Path):
    return WSI(filepath)


@router.get('/metadata')
def metadata(request: Request, filepath: str) -> WSI.metadata_class:
    workspace = request.app.state.settings.workspace
    filepath = resolve_path(workspace, filepath)
    wsi = get_wsi_instance(filepath)
    return wsi.metadata


@router.get('/tile')
def tile(request: Request, filepath: str, level: int, row: int, column: int):
    workspace = request.app.state.settings.workspace
    filepath = resolve_path(workspace, filepath)
    wsi = get_wsi_instance(filepath)
    im = wsi.get_tile(level, row, column)
    buffer = io.BytesIO()
    im.save(buffer, format='PNG')
    return Response(buffer.getvalue(), media_type='image/png')
