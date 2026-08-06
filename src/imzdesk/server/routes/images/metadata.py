import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from imzdesk.io import CLASSES, ImageBase
from imzdesk.server.schema.images import metadata as schema
from imzdesk.server.utils.executor import threaded
from imzdesk.server.utils.filesystem import resolve_filetype, resolve_path

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get('/all')
async def get_metadata(request: Request, filepath: str):
    workspace = request.app.state.settings.workspace
    filepath = await resolve_path(workspace, filepath)
    return await get_metadata_impl(request, filepath)


@threaded
def get_metadata_impl(filepath: Path):
    metadata = image_class_for(filepath).read_metadata(filepath)
    logger.debug('Read image metadata path=%s metadata_type=%s', filepath, type(metadata).__name__)
    return metadata


@router.get('/crop')
async def get_crop(request: Request, filepath: str):
    workspace = request.app.state.settings.workspace
    filepath = await resolve_path(workspace, filepath)
    return await get_crop_impl(request, filepath)


@threaded
def get_crop_impl(filepath: Path):
    crop = getattr(image_class_for(filepath).read_metadata(filepath), 'crop', None)
    logger.debug('Read crop metadata path=%s configured=%s', filepath, crop is not None)
    return crop


@router.put('/crop')
async def put_crop(request: Request, filepath: str, metadata: schema.CropMetadataRequest):
    workspace = request.app.state.settings.workspace
    filepath = await resolve_path(workspace, filepath)
    return await put_crop_impl(request, filepath, metadata)


@threaded
def put_crop_impl(filepath: Path, metadata: schema.CropMetadataRequest):
    image_class = image_class_for(filepath)
    current = image_class.read_metadata(filepath)
    if not hasattr(current, 'crop'):
        logger.warning('Image metadata does not support cropping path=%s', filepath)
        return None
    current.crop = metadata.crop
    crop = image_class.write_metadata(filepath, current).crop
    logger.info('Updated crop metadata path=%s configured=%s', filepath, crop is not None)
    logger.debug('Crop metadata value path=%s crop=%s', filepath, crop)
    return crop


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
    result = image_class.write_metadata(filepath, current)
    logger.info('Set optional metadata path=%s key=%s', filepath, metadata.key)
    return result


@router.delete('/optional')
async def delete_optional_metadata(request: Request, filepath: str, key: str):
    workspace = request.app.state.settings.workspace
    filepath = await resolve_path(workspace, filepath)
    return await delete_optional_metadata_impl(request, filepath, key)


@threaded
def delete_optional_metadata_impl(filepath: Path, key: str):
    image_class = image_class_for(filepath)
    current = image_class.read_metadata(filepath)
    existed = key in current.optional
    current.optional.pop(key, None)
    result = image_class.write_metadata(filepath, current)
    if existed:
        logger.info('Deleted optional metadata path=%s key=%s', filepath, key)
    else:
        logger.warning('Optional metadata was already absent path=%s key=%s', filepath, key)
    return result


def image_class_for(filepath: Path) -> type[ImageBase]:
    filetype = resolve_filetype(filepath)
    if filetype is None:
        logger.warning('Unsupported image type for metadata path=%s', filepath)
        raise HTTPException(status_code=400, detail='Unsupported image file type.')
    logger.debug('Resolved metadata image class path=%s type=%s', filepath, filetype)
    return CLASSES[filetype]
