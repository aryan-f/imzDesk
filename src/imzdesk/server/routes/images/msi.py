import functools
import io
import logging
import pathlib
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from imzdesk.io import MSI
from imzdesk.server.utils.filesystem import resolve_path
from imzdesk.transforms import Bin, NMF, PCA, TIC, TSNE, Normalize, ToDense, ToRImage
from imzdesk.visualization import DImageDisplay

router = APIRouter()
logger = logging.getLogger(__name__)


class PreprocessingSettings(BaseModel):
    normalization: str = 'tic'
    centroiding: str = 'none'
    baselineCorrection: bool = False
    smoothing: bool = False


class CubingSettings(BaseModel):
    method: Literal['binning', 'dreams'] = 'binning'
    mzMin: float = 50.0
    mzMax: float = 1000.0
    binWidth: float = 0.1
    model: str = 'dreams'


class ReductionSettings(BaseModel):
    method: Literal['tic', 'pca', 'nmf', 'tsne', 'umap'] = 'tic'
    components: int = 1
    scaling: str = 'robust'
    colormap: str = 'viridis'


class MSIImageRequest(BaseModel):
    filepath: str
    preprocessing: PreprocessingSettings = Field(default_factory=PreprocessingSettings)
    cubing: CubingSettings = Field(default_factory=CubingSettings)
    reduction: ReductionSettings = Field(default_factory=ReductionSettings)


# Keep an LRU cache for consecutive file access.
@functools.lru_cache(maxsize=4)
def get_msi_instance(filepath: pathlib.Path):
    return MSI(filepath, cache_portable=False)


@router.get('/metadata')
def metadata(request: Request, filepath: str) -> MSI.metadata_class:
    workspace = request.app.state.settings.workspace
    filepath = resolve_path(workspace, filepath)
    wsi = get_msi_instance(filepath)
    return wsi.metadata


@router.post('/image')
def image(request: Request, settings: MSIImageRequest):
    workspace = request.app.state.settings.workspace
    filepath = resolve_path(workspace, settings.filepath)
    msi = get_msi_instance(filepath)
    ragged_image = ToRImage()(msi)
    normalized = Normalize(settings.preprocessing.normalization)(ragged_image)
    if settings.cubing.method != 'binning':
        raise NotImplementedError('DreaMS embeddings are not implemented yet.')
    binned = Bin(
        minimum_channel=settings.cubing.mzMin,
        maximum_channel=settings.cubing.mzMax,
        bin_width=settings.cubing.binWidth,
    )(normalized)
    if settings.reduction.method == 'tic':
        dense_image = TIC()(binned)
    elif settings.reduction.method == 'pca':
        dense_image = PCA(number_of_components=settings.reduction.components)(ToDense()(binned))
    elif settings.reduction.method == 'nmf':
        dense_image = NMF(number_of_components=settings.reduction.components)(binned)
    elif settings.reduction.method == 'tsne':
        dense_image = TSNE(number_of_components=settings.reduction.components)(ToDense()(binned))
    else:
        raise NotImplementedError('UMAP is not implemented yet.')
    buffer = io.BytesIO()
    DImageDisplay(dense_image, colormap=settings.reduction.colormap).save(buffer, format='PNG')
    return Response(buffer.getvalue(), media_type='image/png')
