from typing import Literal

from pydantic import BaseModel, Field


class Annotation(BaseModel):
    id: str | None = None
    label: str = 'positive'
    kind: Literal['box', 'polygon', 'freehand'] = 'box'
    notes: str = ''
    export: bool = True
    project: bool = True
    coordinates: list[list[float]] = Field(default_factory=list)


class AnnotationPatch(BaseModel):
    label: str | None = None
    notes: str | None = None
    export: bool | None = None
    project: bool | None = None
