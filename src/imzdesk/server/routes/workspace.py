import logging
from pathlib import Path

import yaml
from fastapi import APIRouter, Request

from imzdesk.core.workspace import workspace_path
from imzdesk.server.schema.workspace import WorkspaceSettings
from imzdesk.server.utils.executor import threaded

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get('/settings')
async def get_settings(request: Request):
    return await get_settings_impl(request, request.app.state.settings.workspace)


@threaded
def get_settings_impl(workspace: Path):
    path = settings_path(workspace)
    if not path.exists():
        settings = WorkspaceSettings()
        write_settings_file(path, settings)
        logger.info('Created default workspace settings path=%s labels=%d', path, len(settings.labels))
        return settings
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    settings = WorkspaceSettings(**(data or {}))
    logger.debug('Loaded workspace settings path=%s labels=%d', path, len(settings.labels))
    return settings


@router.post('/settings')
async def post_settings(request: Request, settings: WorkspaceSettings):
    return await post_settings_impl(request, request.app.state.settings.workspace, settings)


@threaded
def post_settings_impl(workspace: Path, settings: WorkspaceSettings):
    write_settings_file(settings_path(workspace), settings)
    logger.info('Updated workspace settings workspace=%s labels=%d', workspace, len(settings.labels))
    return settings


def settings_path(workspace: Path):
    path = workspace_path(workspace, 'workspace.yaml')
    logger.debug('Resolved workspace settings path=%s', path)
    return path


def write_settings_file(path: Path, settings: WorkspaceSettings):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(settings.model_dump(mode='json'), f, sort_keys=False)
    logger.debug('Wrote workspace settings path=%s labels=%d', path, len(settings.labels))
