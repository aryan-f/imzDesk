from fastapi import APIRouter

from . import (
    wsi,
)

router = APIRouter()
router.include_router(wsi.router, prefix='/wsi')
