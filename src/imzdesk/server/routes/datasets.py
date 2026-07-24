import os
import stat
from pathlib import Path

import yaml
from fastapi import APIRouter, Request

from imzdesk.data import DatasetManifest
from imzdesk.io import CLASSES
from imzdesk.core.workspace import workspace_path
from imzdesk.server.schema.workspace import WorkspaceSettings
from imzdesk.server.utils.executor import threaded
from imzdesk.server.utils.filesystem import resolve_filetype

router = APIRouter()


@router.get('/manifest')
async def get_manifest(request: Request):
    return await get_manifest_impl(request, request.app.state.settings.workspace)


@threaded
def get_manifest_impl(workspace: Path):
    return DatasetManifest.list_workspace(workspace)


@router.get('/manifest/{dataset_id}')
async def get_dataset_manifest(request: Request, dataset_id: str):
    return await get_dataset_manifest_impl(request, request.app.state.settings.workspace, dataset_id)


@threaded
def get_dataset_manifest_impl(workspace: Path, dataset_id: str):
    return DatasetManifest.from_workspace(workspace, dataset_id)


@router.post('/manifest')
async def post_manifest(request: Request, manifest: DatasetManifest):
    return await post_manifest_impl(request, request.app.state.settings.workspace, manifest)


@threaded
def post_manifest_impl(workspace: Path, manifest: DatasetManifest):
    manifest.to_workspace(workspace)
    return manifest


@router.delete('/manifest/{dataset_id}')
async def delete_dataset_manifest(request: Request, dataset_id: str):
    return await delete_dataset_manifest_impl(request, request.app.state.settings.workspace, dataset_id)


@threaded
def delete_dataset_manifest_impl(workspace: Path, dataset_id: str):
    DatasetManifest.delete_workspace(workspace, dataset_id)
    return True


@router.get('/files')
async def get_files(request: Request):
    return await get_files_impl(request, request.app.state.settings.workspace)


@threaded
def get_files_impl(workspace: Path):
    entries = []
    files = []
    settings_path = workspace_path(workspace, 'workspace.yaml')
    if settings_path.exists():
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings = WorkspaceSettings(**(yaml.safe_load(f) or {}))
    else:
        settings = WorkspaceSettings()
    labels = {label.id: label for label in settings.labels}
    for parent, directories, filenames in os.walk(workspace):
        directories[:] = [directory for directory in directories if not directory.startswith('.')]
        parent = Path(parent)
        for filename in filenames:
            if filename.startswith('.'):
                continue
            path = parent / filename
            filetype = resolve_filetype(path)
            if filetype is None:
                continue
            info = path.stat()
            if not stat.S_ISREG(info.st_mode):
                continue
            files.append((path, filetype, info.st_size))
    wsi_by_name_and_parent = {
        (path.name, path.parent): path
        for path, filetype, _ in files
        if filetype == 'WSI'
    }
    for path, filetype, size in files:
        image_class = CLASSES[filetype]
        annotations = image_class.read_annotations(path)
        annotation_labels = {}
        for annotation in annotations:
            label = annotation.get('label')
            if label and label in labels:
                annotation_labels[label] = annotation_labels.get(label, 0) + 1
        entry = {
            'name': path.name,
            'path': str(path.relative_to(workspace)),
            'directory': False,
            'parent': str(path.parent.relative_to(workspace)),
            'size': size,
            'type': filetype,
            'tags': image_class.read_tags(path),
            'annotation_labels': [
                {
                    'id': label,
                    'name': labels[label].name,
                    'count': count,
                    'color': labels[label].color,
                }
                for label, count in sorted(annotation_labels.items(), key=lambda item: labels[item[0]].name.lower())
            ],
        }
        if filetype == 'MSI':
            derived_directory = image_class.derived_path_for(path, '').parent
            references = []
            if derived_directory.exists():
                for transform_path in derived_directory.glob(f'{path.stem}.*.transform.npy'):
                    reference_name = transform_path.name.removeprefix(f'{path.stem}.').removesuffix('.transform.npy')
                    reference = wsi_by_name_and_parent.get((reference_name, path.parent))
                    if reference is not None:
                        references.append(str(reference.relative_to(workspace)))
            entry['registered_references'] = sorted(references)
        entries.append(entry)
    return sorted(entries, key=lambda entry: (entry['parent'].lower(), entry['name'].lower()))
