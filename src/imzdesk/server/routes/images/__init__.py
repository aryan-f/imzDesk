from fastapi import APIRouter

from . import annotations, metadata, msi, tags, wsi

router = APIRouter()
router.include_router(msi.router, prefix='/msi')
router.include_router(wsi.router, prefix='/wsi')
router.include_router(metadata.router, prefix='/metadata')
router.include_router(tags.router, prefix='/tags')
router.include_router(annotations.router, prefix='/annotations')
