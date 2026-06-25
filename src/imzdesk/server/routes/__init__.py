from fastapi import APIRouter

from . import (
    filesystem,
    system,
)

router = APIRouter()
router.include_router(system.router, prefix='/system')
router.include_router(filesystem.router, prefix='/filesystem')
