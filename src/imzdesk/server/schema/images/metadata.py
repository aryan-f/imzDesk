from pydantic import BaseModel

from imzdesk.core.metadata import MetadataValue


class OptionalMetadataRequest(BaseModel):
    key: str
    value: MetadataValue
