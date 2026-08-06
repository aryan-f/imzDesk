import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from imzdesk.server.logging import CustomHandler
from imzdesk.server.routes import router as api_router
from imzdesk.server.settings import Settings

logger = logging.getLogger(__name__)


class NuxtSPA(StaticFiles):

    async def get_response(self, path: str, scope):
        try:
            # Try to serve the file as-is.
            return await super().get_response(path, scope)
        except HTTPException as exception:
            if exception.status_code == 404:
                # Fall back to index.html for SPA routing.
                logger.debug('Falling back to SPA index for path=%s', path)
                return await super().get_response('index.html', scope)
            logger.warning('Static file request failed path=%s status=%d', path, exception.status_code)
            raise


def create_app():
    settings = Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        loop = asyncio.get_running_loop()

        app.state.settings = settings

        # Logging Broker
        custom_handler = CustomHandler(loop, settings.log_level)
        package_logger = logging.getLogger('imzdesk')
        package_logger.setLevel(settings.log_level)
        package_logger.addHandler(custom_handler)
        app.state.broker = custom_handler.broker

        logger.info(
            'Starting server workspace=%s log_level=%s workers=%d batch_size=%d device=%s',
            settings.workspace,
            logging.getLevelName(settings.log_level) if isinstance(settings.log_level, int) else settings.log_level,
            settings.max_workers,
            settings.batch_size,
            settings.device,
        )

        # Worker Threads
        app.state.executor = ThreadPoolExecutor(
            max_workers=settings.max_workers,
            thread_name_prefix='imzDeskWorkerThread',
        )
        logger.debug('Worker thread pool initialized max_workers=%d', settings.max_workers)
        try:
            yield  # Back to the actual FastAPI app
        finally:
            logger.info('Stopping server and waiting for worker threads')
            app.state.executor.shutdown(wait=True, cancel_futures=True)
            logger.debug('Worker thread pool stopped')
            logger.info('Server stopped')
            package_logger.removeHandler(custom_handler)
            custom_handler.broker.stop()

    app = FastAPI(title='imzDesk', lifespan=lifespan)

    @app.middleware('http')
    async def log_request(request: Request, call_next):
        started = time.perf_counter()
        client = request.client.host if request.client else '<unknown>'
        logger.debug(
            'HTTP request started method=%s path=%s query=%s client=%s',
            request.method,
            request.url.path,
            request.url.query,
            client,
        )
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                'HTTP request failed method=%s path=%s client=%s duration_ms=%.2f',
                request.method,
                request.url.path,
                client,
                (time.perf_counter() - started) * 1000,
            )
            raise
        logger.debug(
            'HTTP request completed method=%s path=%s status=%d client=%s duration_ms=%.2f',
            request.method,
            request.url.path,
            response.status_code,
            client,
            (time.perf_counter() - started) * 1000,
        )
        return response

    # Bind the API endpoints
    app.include_router(api_router, prefix='/api')

    # Fallback to Nuxt on every else
    ui_dir = Path(__file__).parent / 'ui'
    app.mount('/', NuxtSPA(directory=ui_dir, html=True), name="ui")

    return app
