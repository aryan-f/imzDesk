from pathlib import Path

import yaml
from fastapi import APIRouter, Request

from imzdesk.core.workspace import workspace_path
from imzdesk.server.schema.workspace import WorkspaceSettings
from imzdesk.server.utils.executor import threaded

router = APIRouter()


@router.get('/settings')
async def get_settings(request: Request):
    return await get_settings_impl(request, request.app.state.settings.workspace)


@threaded
def get_settings_impl(workspace: Path):
    path = settings_path(workspace)
    if not path.exists():
        settings = WorkspaceSettings()
        write_settings_file(path, settings)
        return settings
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    return WorkspaceSettings(**(data or {}))


@router.post('/settings')
async def post_settings(request: Request, settings: WorkspaceSettings):
    return await post_settings_impl(request, request.app.state.settings.workspace, settings)


@threaded
def post_settings_impl(workspace: Path, settings: WorkspaceSettings):
    write_settings_file(settings_path(workspace), settings)
    return settings


def settings_path(workspace: Path):
    return workspace_path(workspace, 'workspace.yaml')


def write_settings_file(path: Path, settings: WorkspaceSettings):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(settings.model_dump(mode='json'), f, sort_keys=False)
