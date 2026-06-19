from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class Crop(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(ge=1)
    height: int = Field(ge=1)


class Dimensions(BaseModel):
    x: int | float = Field(ge=0)
    y: int | float = Field(ge=0)


class Meta(BaseModel):
    """
    Metadata object for an image.

    Attributes
    ----------
    width: int
        Width of the image in pixels.
    height: int
        Height of the image in pixels.
    mpp: Dimensions
        Microns per pixel.
    crop: Crop
        Target crop.
    """

    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    mpp: Dimensions | None = None
    crop: Crop | None = None

    @classmethod
    def from_file(cls, path: Path):
        if not path.exists():
            return cls()
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        if data is None:
            data = {}
        return cls(**data)

    def to_file(self, path: Path) -> None:
        data = self.model_dump(mode='json')
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, sort_keys=False)
