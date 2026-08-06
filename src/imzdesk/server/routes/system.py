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
    logger.debug('Health check succeeded')
    return {'ok': True}


@router.get('/infra')
async def infra(request: Request):
    workspace = request.app.state.settings.workspace
    logger.debug('Serving infrastructure details workspace=%s', workspace)
    return {'workspace': workspace}


@router.get('/metrics', response_class=EventSourceResponse)
async def metrics(request: Request):
    client = request.client.host if request.client else '<unknown>'
    logger.info('Metrics stream connected client=%s', client)
    psutil.cpu_percent(interval=None)
    try:
        while True:
            if await request.is_disconnected():
                return
            cpu_usage = psutil.cpu_percent(interval=None)
            memory_info = memory_metrics()
            logger.debug(
                'Publishing system metrics client=%s cpu_percent=%.1f memory_percent=%.2f',
                client,
                cpu_usage,
                memory_info['usage_percent'],
            )
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
    finally:
        logger.info('Metrics stream disconnected client=%s', client)


@router.get('/logs', response_class=EventSourceResponse)
async def logs(request: Request):
    client = request.client.host if request.client else '<unknown>'
    logger.info('Log stream connected client=%s', client)
    try:
        async for record in request.app.state.broker.subscribe():
            if await request.is_disconnected():
                return
            yield record
    finally:
        logger.info('Log stream disconnected client=%s', client)
