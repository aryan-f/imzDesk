import numpy as np
from pydantic import BaseModel


class SpectrumBounds(BaseModel):
    x_min: float = -np.inf
    x_max: float = np.inf
    y_min: float = -np.inf
    y_max: float = np.inf
