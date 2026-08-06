import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from imzdesk.io import CLASSES, ImageBase
from imzdesk.server.schema.images import annotations as schema
from imzdesk.server.utils.executor import threaded
from imzdesk.server.utils.filesystem import resolve_filetype, resolve_path

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get('/all')
async def get_annotations(request: Request, filepath: str):
    workspace = request.app.state.settings.workspace
    filepath = await resolve_path(workspace, filepath)
    return await get_annotations_impl(request, filepath)


@threaded
def get_annotations_impl(filepath: Path):
    annotations = image_class_for(filepath).read_annotations(filepath)
    logger.debug('Read annotations path=%s count=%d', filepath, len(annotations))
    return annotations


@router.post('')
async def post_annotation(request: Request, filepath: str, annotation: schema.Annotation):
    workspace = request.app.state.settings.workspace
    filepath = await resolve_path(workspace, filepath)
    return await post_annotation_impl(request, filepath, annotation)


@threaded
def post_annotation_impl(filepath: Path, annotation: schema.Annotation):
    image_class = image_class_for(filepath)
    annotations = image_class.read_annotations(filepath)
    value = annotation.model_dump()
    value['id'] = value['id'] or uuid.uuid4().hex
    annotations.append(value)
    result = image_class.write_annotations(filepath, annotations)
    logger.info(
        'Created annotation path=%s annotation_id=%s kind=%s label=%s total=%d',
        filepath,
        value['id'],
        value['kind'],
        value['label'],
        len(annotations),
    )
    return result


@router.put('/{annotation_id}')
async def put_annotation(request: Request, filepath: str, annotation_id: str, patch: schema.AnnotationPatch):
    workspace = request.app.state.settings.workspace
    filepath = await resolve_path(workspace, filepath)
    return await put_annotation_impl(request, filepath, annotation_id, patch)


@threaded
def put_annotation_impl(filepath: Path, annotation_id: str, patch: schema.AnnotationPatch):
    image_class = image_class_for(filepath)
    annotations = image_class.read_annotations(filepath)
    values = patch.model_dump(exclude_none=True)
    for annotation in annotations:
        if annotation.get('id') == annotation_id:
            annotation.update(values)
            result = image_class.write_annotations(filepath, annotations)
            logger.info(
                'Updated annotation path=%s annotation_id=%s fields=%s',
                filepath,
                annotation_id,
                sorted(values),
            )
            return result
    logger.warning('Annotation not found for update path=%s annotation_id=%s', filepath, annotation_id)
    raise HTTPException(status_code=404, detail='Annotation not found.')


@router.delete('/{annotation_id}')
async def delete_annotation(request: Request, filepath: str, annotation_id: str):
    workspace = request.app.state.settings.workspace
    filepath = await resolve_path(workspace, filepath)
    return await delete_annotation_impl(request, filepath, annotation_id)


@threaded
def delete_annotation_impl(filepath: Path, annotation_id: str):
    image_class = image_class_for(filepath)
    current = image_class.read_annotations(filepath)
    annotations = [annotation for annotation in current if annotation.get('id') != annotation_id]
    result = image_class.write_annotations(filepath, annotations)
    removed = len(current) - len(annotations)
    if removed:
        logger.info('Deleted annotation path=%s annotation_id=%s remaining=%d', filepath, annotation_id, len(annotations))
    else:
        logger.warning('Annotation was already absent path=%s annotation_id=%s', filepath, annotation_id)
    return result


def image_class_for(filepath: Path) -> type[ImageBase]:
    filetype = resolve_filetype(filepath)
    if filetype is None:
        logger.warning('Unsupported image type for annotations path=%s', filepath)
        raise HTTPException(status_code=400, detail='Unsupported image file type.')
    logger.debug('Resolved annotation image class path=%s type=%s', filepath, filetype)
    return CLASSES[filetype]
