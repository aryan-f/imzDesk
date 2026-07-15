from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Request

from imzdesk.io import CLASSES, ImageBase
from imzdesk.server.utils.executor import threaded
from imzdesk.server.utils.filesystem import resolve_filetype, resolve_path

router = APIRouter()


@router.get('/all')
async def get_tags(request: Request, filepath: str):
    workspace = request.app.state.settings.workspace
    filepath = await resolve_path(workspace, filepath)
    return await get_tags_impl(request, filepath)


@threaded
def get_tags_impl(filepath: Path):
    return image_class_for(filepath).read_tags(filepath)


@router.post('')
async def post_tag(request: Request, filepath: str, tag: Annotated[str, Body(embed=True)]):
    workspace = request.app.state.settings.workspace
    filepath = await resolve_path(workspace, filepath)
    return await post_tag_impl(request, filepath, tag)


@threaded
def post_tag_impl(filepath: Path, tag: str):
    image_class = image_class_for(filepath)
    tags = image_class.read_tags(filepath)
    value = tag.strip()
    if value and value not in tags:
        tags.append(value)
    return image_class.write_tags(filepath, tags)


@router.delete('')
async def delete_tag(request: Request, filepath: str, tag: str):
    workspace = request.app.state.settings.workspace
    filepath = await resolve_path(workspace, filepath)
    return await delete_tag_impl(request, filepath, tag)


@threaded
def delete_tag_impl(filepath: Path, tag: str):
    image_class = image_class_for(filepath)
    tags = [value for value in image_class.read_tags(filepath) if value != tag]
    return image_class.write_tags(filepath, tags)


def image_class_for(filepath: Path) -> type[ImageBase]:
    filetype = resolve_filetype(filepath)
    if filetype is None:
        raise HTTPException(status_code=400, detail='Unsupported image file type.')
    return CLASSES[filetype]
