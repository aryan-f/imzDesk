import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Request

from imzdesk.io import CLASSES, ImageBase
from imzdesk.server.utils.executor import threaded
from imzdesk.server.utils.filesystem import resolve_filetype, resolve_path

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get('/all')
async def get_tags(request: Request, filepath: str):
    workspace = request.app.state.settings.workspace
    filepath = await resolve_path(workspace, filepath)
    return await get_tags_impl(request, filepath)


@threaded
def get_tags_impl(filepath: Path):
    tags = image_class_for(filepath).read_tags(filepath)
    logger.debug('Read image tags path=%s count=%d', filepath, len(tags))
    return tags


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
        logger.info('Added image tag path=%s tag=%s total=%d', filepath, value, len(tags))
    elif not value:
        logger.warning('Ignored empty image tag path=%s', filepath)
    else:
        logger.debug('Image tag already exists path=%s tag=%s', filepath, value)
    return image_class.write_tags(filepath, tags)


@router.delete('')
async def delete_tag(request: Request, filepath: str, tag: str):
    workspace = request.app.state.settings.workspace
    filepath = await resolve_path(workspace, filepath)
    return await delete_tag_impl(request, filepath, tag)


@threaded
def delete_tag_impl(filepath: Path, tag: str):
    image_class = image_class_for(filepath)
    current = image_class.read_tags(filepath)
    tags = [value for value in current if value != tag]
    result = image_class.write_tags(filepath, tags)
    if len(tags) != len(current):
        logger.info('Deleted image tag path=%s tag=%s remaining=%d', filepath, tag, len(tags))
    else:
        logger.warning('Image tag was already absent path=%s tag=%s', filepath, tag)
    return result


def image_class_for(filepath: Path) -> type[ImageBase]:
    filetype = resolve_filetype(filepath)
    if filetype is None:
        logger.warning('Unsupported image type for tags path=%s', filepath)
        raise HTTPException(status_code=400, detail='Unsupported image file type.')
    logger.debug('Resolved tag image class path=%s type=%s', filepath, filetype)
    return CLASSES[filetype]
