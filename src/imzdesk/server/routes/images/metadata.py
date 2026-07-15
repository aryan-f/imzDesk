from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from imzdesk.io import CLASSES, ImageBase
from imzdesk.server.schema.images import metadata as schema
from imzdesk.server.utils.executor import threaded
from imzdesk.server.utils.filesystem import resolve_filetype, resolve_path

router = APIRouter()


@router.get('/all')
async def get_metadata(request: Request, filepath: str):
    workspace = request.app.state.settings.workspace
    filepath = await resolve_path(workspace, filepath)
    return await get_metadata_impl(request, filepath)


@threaded
def get_metadata_impl(filepath: Path):
    return image_class_for(filepath).read_metadata(filepath)


@router.post('/optional')
async def post_optional_metadata(request: Request, filepath: str, metadata: schema.OptionalMetadataRequest):
    workspace = request.app.state.settings.workspace
    filepath = await resolve_path(workspace, filepath)
    return await post_optional_metadata_impl(request, filepath, metadata)


@threaded
def post_optional_metadata_impl(filepath: Path, metadata: schema.OptionalMetadataRequest):
    image_class = image_class_for(filepath)
    current = image_class.read_metadata(filepath)
    current.optional[metadata.key] = metadata.value
    return image_class.flush_metadata(filepath, current)


@router.delete('/optional')
async def delete_optional_metadata(request: Request, filepath: str, key: str):
    workspace = request.app.state.settings.workspace
    filepath = await resolve_path(workspace, filepath)
    return await delete_optional_metadata_impl(request, filepath, key)


@threaded
def delete_optional_metadata_impl(filepath: Path, key: str):
    image_class = image_class_for(filepath)
    current = image_class.read_metadata(filepath)
    current.optional.pop(key, None)
    return image_class.flush_metadata(filepath, current)


def image_class_for(filepath: Path) -> type[ImageBase]:
    filetype = resolve_filetype(filepath)
    if filetype is None:
        raise HTTPException(status_code=400, detail='Unsupported image file type.')
    return CLASSES[filetype]
