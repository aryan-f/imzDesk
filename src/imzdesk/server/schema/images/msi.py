from typing import Literal

from pydantic import BaseModel, Field, model_validator


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
    scaling: Literal['robust', 'minmax', 'zscore'] = 'robust'
    colormap: str = 'viridis'

    @model_validator(mode='after')
    def validate_nmf_scaling(self):
        if self.method == 'nmf' and self.scaling != 'minmax':
            raise ValueError('NMF requires min-max scaling.')
        return self


class MSIImageRequest(BaseModel):
    filepath: str
    preprocessing: PreprocessingSettings = Field(default_factory=PreprocessingSettings)
    cubing: CubingSettings = Field(default_factory=CubingSettings)
    reduction: ReductionSettings = Field(default_factory=ReductionSettings)


class PixelCoordinate(BaseModel):
    x: int
    y: int


class MSISpectrumResponse(BaseModel):
    pixel: PixelCoordinate
    coordinate: PixelCoordinate
    mz: list[float]
    intensities: list[float]


class MSIRegistrationRequest(BaseModel):
    filepath: str
    reference: str


class MSIRegistrationTransformRequest(MSIRegistrationRequest):
    transform: list[list[float]]
