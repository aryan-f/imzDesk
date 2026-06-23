from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    workspace: Path
    max_workers: int = Field(default=4, ge=1)

    @field_validator('workspace')
    @classmethod
    def validate_workspace(cls, value: Path) -> Path:
        value = value.expanduser().resolve()
        if not value.exists():
            raise ValueError(f'Workspace does not exist: {value}')
        if not value.is_dir():
            raise ValueError(f'Workspace is not a directory: {value}')
        return value
