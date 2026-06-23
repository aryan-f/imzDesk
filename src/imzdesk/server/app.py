from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from imzdesk.server.routes import router as api_router
from imzdesk.server.settings import Settings


class NuxtSPA(StaticFiles):

    async def get_response(self, path: str, scope):
        try:
            # Try to serve the file as-is.
            return await super().get_response(path, scope)
        except HTTPException as exception:
            if exception.status_code == 404:
                # Fall back to index.html for SPA routing.
                return await super().get_response('index.html', scope)
            raise


def create_app() -> FastAPI:
    settings = Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.executor = ThreadPoolExecutor(
            max_workers=settings.max_workers,
            thread_name_prefix="imzdesk-worker",
        )
        try:
            yield  # Back to the actual FastAPI app
        finally:
            app.state.executor.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(title='imzDesk', lifespan=lifespan)

    # Bind the API endpoints
    app.include_router(api_router, prefix='/api')

    # Fallback to Nuxt on every else
    ui_dir = Path(__file__).parent / 'ui'
    app.mount('/', NuxtSPA(directory=ui_dir, html=True), name="ui")

    return app
