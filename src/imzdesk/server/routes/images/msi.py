import functools
import logging
import pathlib
import threading
from typing import List

import numpy as np
from fastapi import APIRouter, HTTPException, Request
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


@functools.cache
def get_msi_lock(filepath: pathlib.Path | str):
    return threading.Lock()


@router.post('/image')
async def image(request: Request, params: schema.MSIImageRequest):
    settings = request.app.state.settings
    workspace = settings.workspace
    filepath = await resolve_path(workspace, params.filepath)
    return await image_impl(request, filepath, params, settings.batch_size)


@threaded
def image_impl(filepath: pathlib.Path, params: schema.MSIImageRequest, batch_size: int):
    msi = get_msi_instance(filepath)

    image_path = cache_path(msi, key=params, suffix='.png')

    if image_path.exists():
        return image_response(image_path)

    transforms: List[T.Transform] = [
        T.ToRImage(),
        T.Normalize(params.preprocessing.normalization),
    ]

    match params.cubing.method:
        case 'bin':
            transforms.append(T.Bin(minimum_channel=params.cubing.mzMin, maximum_channel=params.cubing.mzMax, bin_width=params.cubing.binWidth))
        case 'embed':
            transforms.append(T.Embed(model=params.cubing.model, batch_size=batch_size))
        case other:
            raise RuntimeError(f'Unknown cubing method: {other}')

    match params.reduction.method:
        case 'tic':
            transforms.append(T.TIC())
        case 'pca':
            transforms.extend([
                T.ToDense(),
                T.Scale(params.reduction.scaling),
                T.PCA(number_of_components=params.reduction.components)
            ])
        case 'nmf':
            transforms.extend([
                T.Scale(params.reduction.scaling),
                T.NMF(number_of_components=params.reduction.components),
            ])
        case 'tsne':
            transforms.extend([
                T.ToDense(),
                T.Scale(params.reduction.scaling),
                T.TSNE(number_of_components=params.reduction.components)
            ])
        case other:
            raise RuntimeError(f'Unknown reduction method: {other}')

    transform = T.Compose(transforms)
    image = transform(msi)

    display = DImageDisplay(image, colormap=params.reduction.colormap)
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


@router.get('/spectrum', response_model=schema.MSISpectrumResponse)
async def spectrum(request: Request, filepath: str, x: int, y: int):
    workspace = request.app.state.settings.workspace
    filepath = await resolve_path(workspace, filepath)
    return await spectrum_impl(request, filepath, x, y)


@threaded
def spectrum_impl(filepath: pathlib.Path, x: int, y: int):
    if x < 0 or y < 0:
        raise HTTPException(status_code=404, detail='The selected MSI pixel does not exist.')

    msi = get_msi_instance(filepath)
    coordinates = np.asarray(msi.coordinates)
    if coordinates.ndim != 2 or coordinates.shape[0] == 0 or coordinates.shape[1] < 2:
        raise HTTPException(status_code=404, detail='The MSI does not contain spatial coordinates.')

    minimum = coordinates[:, :2].min(axis=0).astype(np.int64)
    native_x = int(minimum[0] + x)
    native_y = int(minimum[1] + y)
    try:
        with get_msi_lock(filepath), msi:
            mz, intensities = msi.at(native_x, native_y)
    except ValueError as error:
        raise HTTPException(status_code=404, detail='The selected MSI pixel does not contain a spectrum.') from error

    return {
        'pixel': {'x': x, 'y': y},
        'coordinate': {'x': native_x, 'y': native_y},
        'mz': np.asarray(mz, dtype=np.float64).tolist(),
        'intensities': np.asarray(intensities, dtype=np.float64).tolist(),
    }


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
async def register(request: Request, params: schema.MSIRegistrationRequest):
    settings = request.app.state.settings
    workspace = settings.workspace
    filepath = await resolve_path(workspace, params.filepath)
    reference = await resolve_path(workspace, params.reference)
    return await register_impl(request, filepath, reference, settings.batch_size)


@threaded
def register_impl(filepath: pathlib.Path, reference: pathlib.Path, batch_size: int):
    msi = get_msi_instance(filepath)
    wsi = get_wsi_instance(reference)
    wsi.metadata = wsi.read_metadata(wsi.filepath)
    transform_path = registration_transform_path(msi, reference)
    transform = R.register(wsi, msi, batch_size=batch_size)
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
