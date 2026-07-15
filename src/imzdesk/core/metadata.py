from pathlib import Path

import yaml
from pydantic import BaseModel, Field, computed_field


MetadataValue = str | int | float | bool | None


class BoundingBox(BaseModel):
    x: float = Field(ge=0, lt=1)
    y: float = Field(ge=0, lt=1)
    width: float = Field(ge=0, lt=1)
    height: float = Field(ge=0, lt=1)


class Dimensions(BaseModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)


class Metadata(BaseModel):
    """
    Image metadata.

    Attributes
    ----------
    width: int
        The width of the image.
    height: int
        The height of the image.
    mpp: Dimensions
        Spatial resolution of the image, as microns per pixel.
    """

    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    mpp: Dimensions | None = None
    optional: dict[str, MetadataValue] = Field(default_factory=dict)

    @computed_field
    @property
    def size(self) -> Dimensions | None:  # centimeters
        """
        Size of the image, in centimeters.
        """
        if self.mpp is None or self.width is None or self.height is None:
            return None
        return Dimensions(
            x=round(self.width * self.mpp.x / 10_000, 2),
            y=round(self.height * self.mpp.y / 10_000, 2),
        )

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
