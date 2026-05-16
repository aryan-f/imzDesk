from fastapi import APIRouter

from .filesystem import router as fs_router
from .imzML import router as imzML_router

router = APIRouter()
router.include_router(fs_router, prefix='/fs')
router.include_router(imzML_router, prefix='/imzML')

