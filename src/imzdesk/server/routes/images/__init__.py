from fastapi import APIRouter

from . import msi, wsi

router = APIRouter()
router.include_router(msi.router, prefix='/msi')
router.include_router(wsi.router, prefix='/wsi')
