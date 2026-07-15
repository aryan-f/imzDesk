from pydantic import BaseModel

from imzdesk.core.metadata import BoundingBox, MetadataValue


class OptionalMetadataRequest(BaseModel):
    key: str
    value: MetadataValue


class CropMetadataRequest(BaseModel):
    crop: BoundingBox | None
