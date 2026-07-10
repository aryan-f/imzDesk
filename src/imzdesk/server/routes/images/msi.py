import functools
import io
import logging
import pathlib
from typing import List

from fastapi import APIRouter, Request
from fastapi.responses import Response

import imzdesk.transforms as T
from imzdesk.io import MSI
from imzdesk.server.schema.images import msi as schema
from imzdesk.server.utils.filesystem import resolve_path
from imzdesk.visualization import DImageDisplay

router = APIRouter()
logger = logging.getLogger(__name__)


# Keep an LRU cache for consecutive file access.
@functools.lru_cache(maxsize=4)
def get_msi_instance(filepath: pathlib.Path):
    return MSI(filepath, cache_portable=False)


@router.get('/metadata')
def metadata(request: Request, filepath: str) -> MSI.metadata_class:
    workspace = request.app.state.settings.workspace
    filepath = resolve_path(workspace, filepath)
    wsi = get_msi_instance(filepath)
    return wsi.metadata


@router.post('/image')
def image(request: Request, settings: schema.MSIImageRequest):
    workspace = request.app.state.settings.workspace
    filepath = resolve_path(workspace, settings.filepath)
    msi = get_msi_instance(filepath)

    # TODO: Cache results.

    transforms: List[T.Transform]  = [
        T.ToRImage(),
        T.Normalize(settings.preprocessing.normalization),
    ]

    match settings.cubing.method:
        case 'bin':
            transforms.append(T.Bin(minimum_channel=settings.cubing.mzMin, maximum_channel=settings.cubing.mzMax, bin_width=settings.cubing.binWidth))
        case 'embed':
            transforms.append(T.Embed(model=settings.cubing.model))
        case other:
            logger.error(f'Unknown cubing method: {other}')

    match settings.reduction.method:
        case 'tic':
            transforms.append(T.TIC())
        case 'pca':
            transforms.extend([
                T.ToDense(),
                T.PCA(number_of_components=settings.reduction.components)
            ])
        case 'nmf':
            transforms.append(T.NMF(number_of_components=settings.reduction.components))
        case 'tsne':
            transforms.extend([
                T.ToDense(),
                T.TSNE(number_of_components=settings.reduction.components)
            ])
        case other:
            logger.error(f'Unknown reduction method: {other}')

    transform = T.Compose(transforms)
    image = transform(msi)

    buffer = io.BytesIO()
    display = DImageDisplay(image, colormap=settings.reduction.colormap)
    display.save(buffer, format='PNG')

    return Response(buffer.getvalue(), media_type='image/png')


@router.post('/register')
def register(request: Request, settings: schema.MSIRegistrationRequest) -> schema.MSIRegistrationResponse:
    workspace = request.app.state.settings.workspace
    resolve_path(workspace, settings.filepath)
    resolve_path(workspace, settings.fixed_filepath)
    return schema.MSIRegistrationResponse()
