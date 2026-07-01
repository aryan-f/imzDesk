from enum import Enum

from pydantic import BaseModel


class FileType(str, Enum):
    MSI = 'MSI'
    WSI = 'WSI'


class FilesystemEntry(BaseModel):
    directory: bool
    parent: str
    name: str
    path: str
    size: int | None = None
    type: FileType | None = None
