import asyncio
import sys
import threading
from pathlib import Path

import aiofiles
import aiofiles.os
from fastapi import APIRouter, Body, Query, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent

from .. import schema
from ..services import (
    imzML,
    metadata,
)
from ..utils import (
    raise_on_path,
    get_derived_file_path,
)

router = APIRouter()


@router.get('/converted')
async def converted(request: Request, path: str = Query('.')):
    """
    Checks whether the given .imzML file has yet been converted to an .imz5 file.

    Parameters
    ----------
    request: Request
        FastAPI request object.
    path: str
        Path to the .imzML file.

    Returns
    -------
    exists: bool
        ``True`` if the .imzML file has been converted to an .imz5 file.
    """
    root = request.app.state.root
    target = root / Path(path.lstrip('/'))
    await raise_on_path(target, '.imzML', root=root)
    cached_imz5 = get_derived_file_path(target, '.imz5')
    return await aiofiles.os.path.exists(cached_imz5)


@router.post('/convert', response_class=EventSourceResponse)
async def convert(request: Request, path: str = Query('.')):
    """
    Converts an .imzML file to an .imz5 file.

    The function offloads the heavy computation to a thread that it borrows from the global thread pool, continuously
    sending updates back to the client as **server-sent events**.

    Parameters
    ----------
    request: Request
        FastAPI request object.
    path: str
        The path to the .imzML file.

    Yields
    ------
    ServerSentEvent
        Progress event.
    """
    root = request.app.state.root
    target = root / Path(path.lstrip('/'))
    await raise_on_path(target, '.imzML', root=root)

    events = asyncio.Queue()
    cancelled = threading.Event()
    loop = asyncio.get_running_loop()

    cached_imz5 = get_derived_file_path(target, '.imz5')

    def worker(source, destination, loop, events, cancelled):
        try:
            for event in imzML.convert(source, destination, cancelled=cancelled.is_set):
                loop.call_soon_threadsafe(events.put_nowait, {'event': 'progress', 'data': event})
            loop.call_soon_threadsafe(events.put_nowait, {'event': 'done', 'data': {'phase': 'done', 'progress': 1}})
        except Exception as exception:
            print('Exception occurred in imzML conversion:', exception, file=sys.stderr)
            loop.call_soon_threadsafe(events.put_nowait, {'event': 'error', 'data': {'phase': 'failed', 'message': str(exception)}})
        finally:
            loop.call_soon_threadsafe(events.put_nowait, None)

    loop.run_in_executor(
        request.app.state.thread_pool,
        worker,
        target,
        cached_imz5,
        loop,
        events,
        cancelled,
    )

    is_converting = True

    while is_converting:
        if await request.is_disconnected():
            cancelled.set()
            break
        try:
            event = await asyncio.wait_for(events.get(), timeout=1)
        except asyncio.TimeoutError:
            continue
        if event is None:
            break
        yield ServerSentEvent(
            event=event['event'],
            data=event['data'],
        )


@router.post('/image')
async def image(request: Request, path: str = Query('.'), body: schema.ImageRequest = Body(default=None)):
    """
    Generates a 2D image from an .imzML file.

    Parameters
    ----------
    request: Request
        FastAPI request object.
    path: str
        The path to the .imzML file.
    body: schema.ImageRequest, optional
        Image generation parameters.

    Returns
    -------
    dict
        Containing the generated image.
    """
    root = request.app.state.root
    target = root / Path(path.lstrip('/'))
    await raise_on_path(target, '.imzML', root=root)

    cached_imz5 = get_derived_file_path(target, '.imz5')
    await raise_on_path(cached_imz5, '.imz5')

    body = body or schema.ImageRequest()

    image, (x, y) = await imzML.image_2d(
        cached_imz5,
        **body.model_dump(),
        executor=request.app.state.thread_pool,
    )
    height, width, *channels = image.shape

    return {
        'mode': body.mode,
        'coords': {'x': x.tolist(), 'y': y.tolist()},
        'values': image.tolist(),
        'height': height,
        'width': width,
    }


@router.post('/spectrum')
async def spectrum(request: Request, path: str = Query('.'), body: schema.SpectrumRequest = Body(default=None)):
    """
    Generates a 2D spectrum from an .imzML file.

    Parameters
    ----------
    request: Request
        FastAPI request object.
    path: str
        The path to the .imzML file.
    body: schema.SpectrumRequest, optional
        Specifies the target region in the image.

    Returns
    -------
    dict
        Containing ``"mz"`` and ``"intensity"``.
    """
    root = request.app.state.root
    target = root / Path(path.lstrip('/'))
    await raise_on_path(target, '.imzML', root=root)

    cached_imz5 = get_derived_file_path(target, '.imz5')
    await raise_on_path(cached_imz5, '.imz5')

    body = body or schema.SpectrumRequest()

    spectrum = await imzML.spectrum_2d(
        cached_imz5,
        **body.model_dump(),
        executor=request.app.state.thread_pool
    )

    return spectrum


@router.get('/metadata')
async def get_metadata(request: Request, path: str = Query('.')):
    """
    Returns the associated metadata of an .imzML file.

    Parameters
    ----------
    request: Request
        FastAPI request object.
    path: str
        Path to the .imzML file.

    Returns
    -------
    list
        Contains the metadata as a list of dictionaries, each containing ``"key"`` and ``"value"``.
    """
    root = request.app.state.root
    target = root / Path(path.lstrip('/'))
    await raise_on_path(target, '.imzML', root=root)

    data = await metadata.read(target)

    return [schema.Metadata(key=key, value=value) for key, value in data.items()]


@router.put('/metadata')
async def put_metadata(request: Request, path: str = Query('.'), body: list[schema.Metadata] = Body(default_factory=list),):
    """
    Writes the associated metadata of an .imzML file.

    Parameters
    ----------
    request: Request
        FastAPI request object.
    path: str
        Path to the .imzML file.
    body: list[schema.Metadata]
        Flat metadata rows, each containing ``"key"`` and ``"value"``.

    Returns
    -------
    list
        Saved metadata as a list of dictionaries, each containing ``"key"`` and ``"value"``.
    """
    root = request.app.state.root
    target = root / Path(path.lstrip('/'))
    await raise_on_path(target, '.imzML', root=root)

    data = {}
    for item in body:
        key = item.key.strip()
        data[key] = item.value

    await metadata.write(target, data)

    return [schema.Metadata(key=key, value=value) for key, value in data.items()]