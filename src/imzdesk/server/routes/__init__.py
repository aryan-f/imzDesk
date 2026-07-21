from fastapi import APIRouter

from . import (
    filesystem,
    images,
    system,
    workspace,
)

router = APIRouter()
router.include_router(filesystem.router, prefix='/filesystem')
router.include_router(images.router, prefix='/images')
router.include_router(system.router, prefix='/system')
router.include_router(workspace.router, prefix='/workspace')
