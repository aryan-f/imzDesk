from fastapi import APIRouter

from . import (
    filesystem,
    images,
    system,
)

router = APIRouter()
router.include_router(filesystem.router, prefix='/filesystem')
router.include_router(images.router, prefix='/images')
router.include_router(system.router, prefix='/system')
