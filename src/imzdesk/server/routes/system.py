import logging

import psutil
from fastapi import APIRouter, Request
from fastapi.sse import EventSourceResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get('/health')
def health():
    return {'ok': True}


@router.get('/infra')
def infra(request: Request):
    return {'workspace': request.app.state.settings.workspace}


@router.get('/metrics')
def metrics():
    cpu_usage = psutil.cpu_percent(interval=0.1)  # a quick sample over 100ms
    memory_info = psutil.virtual_memory()  # virtual memory statistics
    return {
        'cpu': {
            'usage_percent': cpu_usage
        },
        'memory': {
            'usage_percent': memory_info.percent,
            'used': round(memory_info.used / (1024 * 1024 * 1024), 2),
            'total': round(memory_info.total / (1024 * 1024 * 1024), 2)
        }
    }


@router.get('/logs', response_class=EventSourceResponse)
async def logs(request: Request):
    async for record in request.app.state.broker.subscribe():
        if await request.is_disconnected():
            return
        yield record
