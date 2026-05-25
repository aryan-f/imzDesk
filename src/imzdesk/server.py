from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import router as api_router


def create_app(root, num_workers):

    def factory() -> FastAPI:
        app = FastAPI(title='imzDesk')

        # Global state
        app.state.root = root

        # Thread Pool
        app.state.thread_pool = ThreadPoolExecutor(max_workers=num_workers)

        # API Endpoints
        app.include_router(api_router, prefix='/api')

        # Built user interface
        ui_dir = Path(__file__).parent / 'ui'
        app.mount('/_nuxt', StaticFiles(directory=ui_dir / '_nuxt'), name='nuxt')
        app.mount('/_fonts', StaticFiles(directory=ui_dir / '_fonts'), name='fonts')
        app.mount('/images', StaticFiles(directory=ui_dir / 'images'), name='images')

        # Fallback for SPA routing
        @app.get('/{full_path:path}')
        async def spa_fallback(full_path: str):
            if full_path.startswith('api/'):
                return {'detail': 'Not found'}
            # Route everything else to the SPA.
            return FileResponse(ui_dir / 'index.html')

        return app

    return factory

