import logging
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
logger = logging.getLogger(__name__)


@router.get('/manifest')
async def get_manifest(request: Request):
    return await get_manifest_impl(request, request.app.state.settings.workspace)


@threaded
def get_manifest_impl(workspace: Path):
    manifests = DatasetManifest.list_workspace(workspace)
    logger.debug('Listed dataset manifests workspace=%s count=%d', workspace, len(manifests))
    return manifests


@router.get('/manifest/{dataset_id}')
async def get_dataset_manifest(request: Request, dataset_id: str):
    return await get_dataset_manifest_impl(request, request.app.state.settings.workspace, dataset_id)


@threaded
def get_dataset_manifest_impl(workspace: Path, dataset_id: str):
    logger.debug('Reading dataset manifest workspace=%s dataset_id=%s', workspace, dataset_id)
    manifest = DatasetManifest.from_workspace(workspace, dataset_id)
    logger.debug('Read dataset manifest dataset_id=%s name=%s kind=%s', manifest.id, manifest.name, manifest.kind)
    return manifest


@router.post('/manifest')
async def post_manifest(request: Request, manifest: DatasetManifest):
    return await post_manifest_impl(request, request.app.state.settings.workspace, manifest)


@threaded
def post_manifest_impl(workspace: Path, manifest: DatasetManifest):
    manifest.to_workspace(workspace)
    sample_count = sum(len(samples) for samples in manifest.splits.values())
    logger.info(
        'Saved dataset manifest dataset_id=%s name=%s kind=%s splits=%d samples=%d',
        manifest.id,
        manifest.name,
        manifest.kind,
        len(manifest.splits),
        sample_count,
    )
    return manifest


@router.delete('/manifest/{dataset_id}')
async def delete_dataset_manifest(request: Request, dataset_id: str):
    return await delete_dataset_manifest_impl(request, request.app.state.settings.workspace, dataset_id)


@threaded
def delete_dataset_manifest_impl(workspace: Path, dataset_id: str):
    path = DatasetManifest.path(workspace, dataset_id)
    existed = path.exists()
    DatasetManifest.delete_workspace(workspace, dataset_id)
    if existed:
        logger.info('Deleted dataset manifest dataset_id=%s path=%s', dataset_id, path)
    else:
        logger.warning('Dataset manifest was already absent dataset_id=%s path=%s', dataset_id, path)
    return True


@router.get('/files')
async def get_files(request: Request):
    return await get_files_impl(request, request.app.state.settings.workspace)


@threaded
def get_files_impl(workspace: Path):
    logger.info('Scanning workspace image files workspace=%s', workspace)
    entries = []
    files = []
    settings_path = workspace_path(workspace, 'workspace.yaml')
    if settings_path.exists():
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings = WorkspaceSettings(**(yaml.safe_load(f) or {}))
        logger.debug('Loaded workspace labels path=%s count=%d', settings_path, len(settings.labels))
    else:
        settings = WorkspaceSettings()
        logger.debug('Workspace settings absent; using default labels path=%s count=%d', settings_path, len(settings.labels))
    labels = {label.id: label for label in settings.labels}
    for parent, directories, filenames in os.walk(workspace):
        hidden_directories = [directory for directory in directories if directory.startswith('.')]
        directories[:] = [directory for directory in directories if not directory.startswith('.')]
        parent = Path(parent)
        if hidden_directories:
            logger.debug('Skipping hidden directories parent=%s names=%s', parent, sorted(hidden_directories))
        for filename in filenames:
            if filename.startswith('.'):
                logger.debug('Skipping hidden file path=%s', parent / filename)
                continue
            path = parent / filename
            filetype = resolve_filetype(path)
            if filetype is None:
                continue
            info = path.stat()
            if not stat.S_ISREG(info.st_mode):
                logger.debug('Skipping non-regular recognized path=%s type=%s', path, filetype)
                continue
            files.append((path, filetype, info.st_size))
            logger.debug('Discovered image file path=%s type=%s size_bytes=%d', path, filetype, info.st_size)
    logger.debug('Workspace scan discovered recognized_files=%d', len(files))
    wsi_by_name_and_parent = {
        (path.name, path.parent): path
        for path, filetype, _ in files
        if filetype == 'WSI'
    }
    for path, filetype, size in files:
        image_class = CLASSES[filetype]
        annotations = image_class.read_annotations(path)
        logger.debug('Read file annotations path=%s count=%d', path, len(annotations))
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
            logger.debug('Resolved MSI registration references path=%s count=%d', path, len(references))
        entries.append(entry)
    entries = sorted(entries, key=lambda entry: (entry['parent'].lower(), entry['name'].lower()))
    logger.info('Completed workspace image scan workspace=%s entries=%d', workspace, len(entries))
    return entries
