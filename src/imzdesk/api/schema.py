from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict


class ImageRequest(BaseModel):
    mode: Literal['tic', 'ion', 'pca', 'kmn'] = 'tic'
    model_config = ConfigDict(extra='allow')


class SpectrumRequest(BaseModel):
    x_min: float = -np.inf
    x_max: float = np.inf
    y_min: float = -np.inf
    y_max: float = np.inf
    precision: float = 1


class Metadata(BaseModel):
    key: str
    value: float | int | str | bool
    original_key: str = None
