import functools
import logging
import pathlib
from typing import List

import numpy as np
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

import imzdesk.transforms as T
import imzdesk.registration as R
from imzdesk.io import MSI
from imzdesk.server.schema.images import msi as schema
from imzdesk.server.utils.caching import cache_path
from imzdesk.server.utils.executor import threaded
from imzdesk.server.utils.filesystem import resolve_path
from imzdesk.visualization import DImageDisplay
from .wsi import get_wsi_instance

router = APIRouter()
logger = logging.getLogger(__name__)


# Keep an LRU cache for consecutive file access.
@functools.lru_cache(maxsize=4)
def get_msi_instance(filepath: pathlib.Path | str):
    return MSI(filepath, cache_portable=False)


@router.post('/image')
async def image(request: Request, settings: schema.MSIImageRequest):
    workspace = request.app.state.settings.workspace
    filepath = await resolve_path(workspace, settings.filepath)
    return await image_impl(request, filepath, settings)


@threaded
def image_impl(filepath: pathlib.Path, settings: schema.MSIImageRequest):
    msi = get_msi_instance(filepath)

    image_path = cache_path(msi, key=settings, suffix='.png')

    if image_path.exists():
        return image_response(image_path)

    transforms: List[T.Transform] = [
        T.ToRImage(),
        T.Normalize(settings.preprocessing.normalization),
    ]

    match settings.cubing.method:
        case 'bin':
            transforms.append(T.Bin(minimum_channel=settings.cubing.mzMin, maximum_channel=settings.cubing.mzMax, bin_width=settings.cubing.binWidth))
        case 'embed':
            transforms.append(T.Embed(model=settings.cubing.model))
        case other:
            raise RuntimeError(f'Unknown cubing method: {other}')

    match settings.reduction.method:
        case 'tic':
            transforms.append(T.TIC())
        case 'pca':
            transforms.extend([
                T.ToDense(),
                T.Scale(settings.reduction.scaling),
                T.PCA(number_of_components=settings.reduction.components)
            ])
        case 'nmf':
            transforms.extend([
                T.Scale(settings.reduction.scaling),
                T.NMF(number_of_components=settings.reduction.components),
            ])
        case 'tsne':
            transforms.extend([
                T.ToDense(),
                T.Scale(settings.reduction.scaling),
                T.TSNE(number_of_components=settings.reduction.components)
            ])
        case other:
            raise RuntimeError(f'Unknown reduction method: {other}')

    transform = T.Compose(transforms)
    image = transform(msi)

    display = DImageDisplay(image, colormap=settings.reduction.colormap)
    display.save(image_path, format='PNG')

    return image_response(image_path)


def image_response(image_path: pathlib.Path):
    cache_key_hash = image_path.stem.rsplit(".", 1)[-1]
    return FileResponse(
        path=image_path,
        media_type='image/png',
        filename=image_path.name,
        headers={
            'Cache-Control': 'public, max-age=31536000, immutable',
            'ETag': f'"{cache_key_hash}"',
        },
    )


@router.get('/registered')
async def registered(request: Request, filepath: str, reference: str):
    workspace = request.app.state.settings.workspace
    filepath = await resolve_path(workspace, filepath)
    reference = await resolve_path(workspace, reference)
    return await registered_impl(request, filepath, reference)


@threaded
def registered_impl(filepath: pathlib.Path, reference: pathlib.Path):
    msi = get_msi_instance(filepath)
    return registration_transform_path(msi, reference).exists()


@router.post('/register')
async def register(request: Request, settings: schema.MSIRegistrationRequest):
    workspace = request.app.state.settings.workspace
    filepath = await resolve_path(workspace, settings.filepath)
    reference = await resolve_path(workspace, settings.reference)
    return await register_impl(request, filepath, reference)


@threaded
def register_impl(filepath: pathlib.Path, reference: pathlib.Path):
    msi = get_msi_instance(filepath)
    wsi = get_wsi_instance(reference)
    wsi.metadata = wsi.read_metadata(wsi.filepath)
    transform_path = registration_transform_path(msi, reference)
    transform = R.register(wsi, msi)
    np.save(transform_path, transform.matrix, allow_pickle=False)
    return True


@router.get('/registered/transform')
async def registered_transform(request: Request, filepath: str, reference: str):
    workspace = request.app.state.settings.workspace
    filepath = await resolve_path(workspace, filepath)
    reference = await resolve_path(workspace, reference)
    return await registered_transform_impl(request, filepath, reference)


@threaded
def registered_transform_impl(filepath: pathlib.Path, reference: pathlib.Path):
    msi = get_msi_instance(filepath)
    transform_path = registration_transform_path(msi, reference)
    if not transform_path.exists():
        return None
    return np.load(transform_path, allow_pickle=False).tolist()


@router.put('/registered/transform')
async def put_registered_transform(request: Request, settings: schema.MSIRegistrationTransformRequest):
    workspace = request.app.state.settings.workspace
    filepath = await resolve_path(workspace, settings.filepath)
    reference = await resolve_path(workspace, settings.reference)
    return await put_registered_transform_impl(request, filepath, reference, settings.transform)


@threaded
def put_registered_transform_impl(filepath: pathlib.Path, reference: pathlib.Path, transform: list[list[float]]):
    msi = get_msi_instance(filepath)
    transform_path = registration_transform_path(msi, reference)
    np.save(transform_path, np.asarray(transform, dtype=np.float64), allow_pickle=False)
    return True


def registration_transform_path(msi: MSI, reference: pathlib.Path):
    return cache_path(msi, suffix=f'.{reference.name}.transform.npy')
