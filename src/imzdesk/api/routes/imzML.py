import asyncio
import sys
import threading
from pathlib import Path

import aiofiles
import aiofiles.os
from fastapi import APIRouter, Body, Query, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent

from .. import schema
from ..services import imzML
from ..utils import (
    raise_on_path,
    get_cached_path,
)

router = APIRouter()


@router.get('/converted')
async def converted(request: Request, path: str = Query('.')):
    root = request.app.state.root
    target = root / Path(path.lstrip('/'))
    await raise_on_path(target, '.imzML', root=root)
    cached_imz5 = get_cached_path(target, '.imz5')
    return await aiofiles.os.path.exists(cached_imz5)


@router.post('/convert', response_class=EventSourceResponse)
async def convert(request: Request, path: str = Query('.')):
    root = request.app.state.root
    target = root / Path(path.lstrip('/'))
    await raise_on_path(target, '.imzML', root=root)

    events = asyncio.Queue()
    cancelled = threading.Event()
    loop = asyncio.get_running_loop()

    cached_imz5 = get_cached_path(target, '.imz5')

    def worker(source, destination, loop, events, cancelled):
        try:
            for event in imzML.imzML_to_imz5(source, destination, cancelled=cancelled.is_set):
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
async def image(request: Request, path: str = Query('.')):
    root = request.app.state.root
    target = root / Path(path.lstrip('/'))
    await raise_on_path(target, '.imzML', root=root)

    cached_imz5 = get_cached_path(target, '.imz5')
    await raise_on_path(cached_imz5, '.imz5')

    # TODO: Implement other modes.

    im = await imzML.tic_from_imz5(cached_imz5, executor=request.app.state.thread_pool)
    height, width = im.shape

    return {
        'mode': 'tic',
        'values': im.tolist(),
        'height': height,
        'width': width,
    }


@router.post('/spectrum')
async def spectrum(request: Request, path: str = Query('.'), bounds: schema.SpectrumBounds = Body(default=None)):
    root = request.app.state.root
    target = root / Path(path.lstrip('/'))
    await raise_on_path(target, '.imzML', root=root)

    cached_imz5 = get_cached_path(target, '.imz5')
    await raise_on_path(cached_imz5, '.imz5')

    bounds = bounds or schema.SpectrumBounds()

    spectrum = await imzML.spectrum(
        cached_imz5,
        **bounds.model_dump(),
        executor=request.app.state.thread_pool
    )

    return spectrum