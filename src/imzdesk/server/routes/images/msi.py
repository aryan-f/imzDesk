import functools
import logging
import pathlib
import threading
import time
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


def cache_info(function):
    info = getattr(function, 'cache_info', None)
    return info() if info is not None else '<unavailable>'


# Keep an LRU cache for consecutive file access.
@functools.lru_cache(maxsize=4)
def get_msi_instance(filepath: pathlib.Path | str):
    logger.debug('Creating cached MSI reader path=%s', filepath)
    return MSI(filepath, cache_portable=False)


@functools.cache
def get_msi_lock(filepath: pathlib.Path | str):
    logger.debug('Creating MSI reader lock path=%s', filepath)
    return threading.Lock()


@router.post('/image')
async def image(request: Request, params: schema.MSIImageRequest):
    settings = request.app.state.settings
    workspace = settings.workspace
    logger.debug('MSI image requested filepath=%s', params.filepath)
    filepath = await resolve_path(workspace, params.filepath)
    return await image_impl(request, filepath, params, settings.batch_size)


@threaded
def image_impl(filepath: pathlib.Path, params: schema.MSIImageRequest, batch_size: int):
    msi = get_msi_instance(filepath)
    logger.debug('Using MSI reader path=%s cache=%s', filepath, cache_info(get_msi_instance))

    image_path = cache_path(msi, key=params, suffix='.png')

    if image_path.exists():
        logger.debug('MSI image cache hit source=%s image=%s', filepath, image_path)
        return image_response(image_path)

    started = time.perf_counter()
    logger.info(
        'Rendering MSI image path=%s normalization=%s cubing=%s reduction=%s',
        filepath,
        params.preprocessing.normalization,
        params.cubing.method,
        params.reduction.method,
    )
    logger.debug(
        'MSI render parameters path=%s cubing=%s reduction=%s batch_size=%d',
        filepath,
        params.cubing.model_dump(mode='json'),
        params.reduction.model_dump(mode='json'),
        batch_size,
    )

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
            logger.error('Unsupported MSI cubing method path=%s method=%s', filepath, other)
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
            logger.error('Unsupported MSI reduction method path=%s method=%s', filepath, other)
            raise RuntimeError(f'Unknown reduction method: {other}')

    logger.debug('Executing MSI transform pipeline path=%s transforms=%s', filepath, [type(item).__name__ for item in transforms])
    transform = T.Compose(transforms)
    image = transform(msi)
    logger.debug('MSI transform pipeline completed path=%s output_type=%s', filepath, type(image).__name__)

    display = DImageDisplay(image, colormap=params.reduction.colormap)
    display.save(image_path, format='PNG')
    logger.info(
        'Rendered MSI image path=%s output=%s duration_ms=%.2f',
        filepath,
        image_path,
        (time.perf_counter() - started) * 1000,
    )

    return image_response(image_path)


def image_response(image_path: pathlib.Path):
    cache_key_hash = image_path.stem.rsplit(".", 1)[-1]
    logger.debug('Serving cached MSI image path=%s etag=%s', image_path, cache_key_hash)
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
    logger.debug('MSI spectrum requested filepath=%s pixel=(%d,%d)', filepath, x, y)
    filepath = await resolve_path(workspace, filepath)
    return await spectrum_impl(request, filepath, x, y)


@threaded
def spectrum_impl(filepath: pathlib.Path, x: int, y: int):
    if x < 0 or y < 0:
        logger.warning('Rejected negative MSI spectrum pixel path=%s pixel=(%d,%d)', filepath, x, y)
        raise HTTPException(status_code=404, detail='The selected MSI pixel does not exist.')

    msi = get_msi_instance(filepath)
    logger.debug('Using MSI reader for spectrum path=%s cache=%s', filepath, cache_info(get_msi_instance))
    coordinates = np.asarray(msi.coordinates)
    if coordinates.ndim != 2 or coordinates.shape[0] == 0 or coordinates.shape[1] < 2:
        logger.warning('MSI has no usable spatial coordinates path=%s shape=%s', filepath, coordinates.shape)
        raise HTTPException(status_code=404, detail='The MSI does not contain spatial coordinates.')

    minimum = coordinates[:, :2].min(axis=0).astype(np.int64)
    native_x = int(minimum[0] + x)
    native_y = int(minimum[1] + y)
    logger.debug(
        'Mapped MSI display pixel path=%s pixel=(%d,%d) native=(%d,%d) coordinate_minimum=(%d,%d)',
        filepath,
        x,
        y,
        native_x,
        native_y,
        minimum[0],
        minimum[1],
    )
    try:
        lock = get_msi_lock(filepath)
        logger.debug('Waiting for MSI reader lock path=%s native=(%d,%d)', filepath, native_x, native_y)
        with lock, msi:
            logger.debug('Acquired MSI reader lock path=%s native=(%d,%d)', filepath, native_x, native_y)
            mz, intensities = msi.at(native_x, native_y)
    except ValueError as error:
        logger.warning('MSI spectrum pixel is unmeasured path=%s native=(%d,%d)', filepath, native_x, native_y)
        raise HTTPException(status_code=404, detail='The selected MSI pixel does not contain a spectrum.') from error

    mz = np.asarray(mz, dtype=np.float64)
    intensities = np.asarray(intensities, dtype=np.float64)
    logger.debug(
        'Loaded MSI spectrum path=%s native=(%d,%d) peaks=%d mz_min=%s mz_max=%s',
        filepath,
        native_x,
        native_y,
        mz.size,
        float(mz.min()) if mz.size else None,
        float(mz.max()) if mz.size else None,
    )

    return {
        'pixel': {'x': x, 'y': y},
        'coordinate': {'x': native_x, 'y': native_y},
        'mz': mz.tolist(),
        'intensities': intensities.tolist(),
    }


@router.get('/registered')
async def registered(request: Request, filepath: str, reference: str):
    workspace = request.app.state.settings.workspace
    logger.debug('MSI registration status requested filepath=%s reference=%s', filepath, reference)
    filepath = await resolve_path(workspace, filepath)
    reference = await resolve_path(workspace, reference)
    return await registered_impl(request, filepath, reference)


@threaded
def registered_impl(filepath: pathlib.Path, reference: pathlib.Path):
    msi = get_msi_instance(filepath)
    path = registration_transform_path(msi, reference)
    exists = path.exists()
    logger.debug('Checked MSI registration path=%s reference=%s transform=%s exists=%s', filepath, reference, path, exists)
    return exists


@router.post('/register')
async def register(request: Request, params: schema.MSIRegistrationRequest):
    settings = request.app.state.settings
    workspace = settings.workspace
    logger.info('MSI registration requested filepath=%s reference=%s', params.filepath, params.reference)
    filepath = await resolve_path(workspace, params.filepath)
    reference = await resolve_path(workspace, params.reference)
    return await register_impl(request, filepath, reference, settings.batch_size)


@threaded
def register_impl(filepath: pathlib.Path, reference: pathlib.Path, batch_size: int):
    started = time.perf_counter()
    logger.info('Registering MSI path=%s reference=%s batch_size=%d', filepath, reference, batch_size)
    msi = get_msi_instance(filepath)
    wsi = get_wsi_instance(reference)
    logger.debug(
        'Using cached readers for registration msi_cache=%s wsi_cache=%s',
        cache_info(get_msi_instance),
        cache_info(get_wsi_instance),
    )
    wsi.metadata = wsi.read_metadata(wsi.filepath)
    logger.debug('Loaded WSI registration metadata reference=%s', reference)
    transform_path = registration_transform_path(msi, reference)
    transform = R.register(wsi, msi, batch_size=batch_size)
    logger.debug('Computed MSI registration matrix path=%s reference=%s matrix=%s', filepath, reference, transform.matrix.tolist())
    np.save(transform_path, transform.matrix, allow_pickle=False)
    logger.info(
        'Saved MSI registration path=%s reference=%s transform=%s duration_ms=%.2f',
        filepath,
        reference,
        transform_path,
        (time.perf_counter() - started) * 1000,
    )
    return True


@router.get('/registered/transform')
async def registered_transform(request: Request, filepath: str, reference: str):
    workspace = request.app.state.settings.workspace
    logger.debug('MSI registration transform requested filepath=%s reference=%s', filepath, reference)
    filepath = await resolve_path(workspace, filepath)
    reference = await resolve_path(workspace, reference)
    return await registered_transform_impl(request, filepath, reference)


@threaded
def registered_transform_impl(filepath: pathlib.Path, reference: pathlib.Path):
    msi = get_msi_instance(filepath)
    transform_path = registration_transform_path(msi, reference)
    if not transform_path.exists():
        logger.debug('MSI registration transform absent path=%s reference=%s transform=%s', filepath, reference, transform_path)
        return None
    transform = np.load(transform_path, allow_pickle=False).tolist()
    logger.debug('Loaded MSI registration transform path=%s reference=%s transform=%s', filepath, reference, transform)
    return transform


@router.put('/registered/transform')
async def put_registered_transform(request: Request, settings: schema.MSIRegistrationTransformRequest):
    workspace = request.app.state.settings.workspace
    logger.info('Manual MSI registration update requested filepath=%s reference=%s', settings.filepath, settings.reference)
    filepath = await resolve_path(workspace, settings.filepath)
    reference = await resolve_path(workspace, settings.reference)
    return await put_registered_transform_impl(request, filepath, reference, settings.transform)


@threaded
def put_registered_transform_impl(filepath: pathlib.Path, reference: pathlib.Path, transform: list[list[float]]):
    msi = get_msi_instance(filepath)
    transform_path = registration_transform_path(msi, reference)
    matrix = np.asarray(transform, dtype=np.float64)
    np.save(transform_path, matrix, allow_pickle=False)
    logger.info('Saved manual MSI registration path=%s reference=%s transform=%s', filepath, reference, transform_path)
    logger.debug('Manual MSI registration matrix path=%s matrix=%s', filepath, matrix.tolist())
    return True


def registration_transform_path(msi: MSI, reference: pathlib.Path):
    path = cache_path(msi, suffix=f'.{reference.name}.transform.npy')
    logger.debug('Resolved registration transform path msi=%s reference=%s path=%s', getattr(msi, 'filepath', '<unknown>'), reference, path)
    return path
