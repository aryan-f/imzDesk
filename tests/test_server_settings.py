import sys

import pytest
from pydantic import ValidationError

import imzdesk.server.entry as entry_module
from imzdesk.server.settings import Settings


def test_batch_size_defaults_to_current_embedding_batch_size(tmp_path, monkeypatch):
    monkeypatch.delenv('BATCH_SIZE', raising=False)

    settings = Settings(workspace=tmp_path)

    assert settings.batch_size == 120


def test_batch_size_can_be_configured_by_environment(tmp_path, monkeypatch):
    monkeypatch.setenv('BATCH_SIZE', '48')

    settings = Settings(workspace=tmp_path)

    assert settings.batch_size == 48


@pytest.mark.parametrize('batch_size', [0, -1])
def test_batch_size_must_be_positive(tmp_path, batch_size):
    with pytest.raises(ValidationError):
        Settings(workspace=tmp_path, batch_size=batch_size)


def test_cli_exports_batch_size_for_application_settings(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        sys,
        'argv',
        ['imzdesk', str(tmp_path), '--batch-size', '64'],
    )
    monkeypatch.setattr(entry_module.uvicorn, 'run', lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.delenv('BATCH_SIZE', raising=False)

    entry_module.run_server()

    assert entry_module.os.environ['BATCH_SIZE'] == '64'
    assert len(calls) == 1
