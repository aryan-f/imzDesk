import logging
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    workspace: Path
    log_level: int | str = logging.INFO
    max_workers: int = Field(default=4, ge=1)
    batch_size: int = Field(default=128, ge=1)
    device: str = 'cuda'

    @field_validator('workspace')
    @classmethod
    def validate_workspace(cls, value: Path) -> Path:
        value = value.expanduser().resolve()
        if not value.exists():
            logger.error('Configured workspace does not exist path=%s', value)
            raise ValueError(f'Workspace does not exist: {value}')
        if not value.is_dir():
            logger.error('Configured workspace is not a directory path=%s', value)
            raise ValueError(f'Workspace is not a directory: {value}')
        logger.debug('Validated workspace path=%s', value)
        return value
