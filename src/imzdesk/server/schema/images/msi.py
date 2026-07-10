from typing import Literal

from pydantic import BaseModel, Field


class PreprocessingSettings(BaseModel):
    normalization: str = 'tic'
    centroiding: str = 'none'
    baselineCorrection: bool = False
    smoothing: bool = False


class CubingSettings(BaseModel):
    method: Literal['bin', 'embed'] = 'bin'
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
    registered: bool = False
    preprocessing: PreprocessingSettings = Field(default_factory=PreprocessingSettings)
    cubing: CubingSettings = Field(default_factory=CubingSettings)
    reduction: ReductionSettings = Field(default_factory=ReductionSettings)


class MSIRegistrationRequest(BaseModel):
    filepath: str
    fixed_filepath: str


class MSIRegistrationResponse(BaseModel):
    registered: bool = True
    cached: bool = True
    transform: list[float] = Field(default_factory=lambda: [1.0, 0.0, 0.0, 0.0, 1.0, 0.0])
