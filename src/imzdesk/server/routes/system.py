import asyncio
import logging

import psutil
from fastapi import APIRouter, Request
from fastapi.sse import EventSourceResponse

from imzdesk.server.utils.system import memory_metrics

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get('/health')
async def health():
    return {'ok': True}


@router.get('/infra')
async def infra(request: Request):
    return {'workspace': request.app.state.settings.workspace}


@router.get('/metrics', response_class=EventSourceResponse)
async def metrics(request: Request):
    psutil.cpu_percent(interval=None)
    while True:
        if await request.is_disconnected():
            return
        cpu_usage = psutil.cpu_percent(interval=None)
        memory_info = memory_metrics()
        yield {
            'data': {
                'cpu': {
                    'usage_percent': cpu_usage
                },
                'memory': {
                    'used': memory_info['used'],
                    'total': memory_info['total'],
                    'usage_percent': memory_info['usage_percent'],
                }
            }
        }
        await asyncio.sleep(2)


@router.get('/logs', response_class=EventSourceResponse)
async def logs(request: Request):
    async for record in request.app.state.broker.subscribe():
        if await request.is_disconnected():
            return
        yield record
