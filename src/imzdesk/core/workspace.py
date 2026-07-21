from pathlib import Path


def workspace_path(root: Path | str, suffix: str) -> Path:
    root = Path(root)
    return root / '.imzDesk' / suffix


def derived_path(filepath: Path | str, suffix: str) -> Path:
    filepath = Path(filepath)
    return workspace_path(filepath.parent, f'{filepath.stem}{suffix}')
