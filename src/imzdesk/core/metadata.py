from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    x: float = Field(ge=0, lt=1)
    y: float = Field(ge=0, lt=1)
    width: float = Field(ge=0, lt=1)
    height: float = Field(ge=0, lt=1)


class Dimensions(BaseModel):
    x: int | float = Field(ge=0)
    y: int | float = Field(ge=0)


class Metadata(BaseModel):

    @classmethod
    def from_file(cls, path: Path):
        if not path.exists():
            raise FileNotFoundError
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


class ImageMetadata(Metadata):
    height: int | None = Field(default=None, ge=1)
    width: int | None = Field(default=None, ge=1)
    mpp: Dimensions | None = None


class WSIMetadata(ImageMetadata):
    crop: BoundingBox | None = None


class MSIMetadata(ImageMetadata):
    pass
