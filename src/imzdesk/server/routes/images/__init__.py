from fastapi import APIRouter

from . import msi, wsi, metadata, tags

router = APIRouter()
router.include_router(msi.router, prefix='/msi')
router.include_router(wsi.router, prefix='/wsi')
router.include_router(metadata.router, prefix='/metadata')
router.include_router(tags.router, prefix='/tags')
