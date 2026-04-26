from fastapi import APIRouter

from .fs import router as fs_router

router = APIRouter()
router.include_router(fs_router, prefix='/fs')

