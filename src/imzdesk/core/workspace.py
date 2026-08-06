from pathlib import Path


def workspace_path(root, suffix):
    """
    Return a path inside the hidden imzDesk workspace directory.

    Parameters
    ----------
    root : pathlib.Path or str
        Workspace root.
    suffix : str
        Path relative to the hidden workspace directory.

    Returns
    -------
    pathlib.Path
        Resolved workspace path.
    """
    root = Path(root)
    return root / '.imzDesk' / suffix


def derived_path(filepath, suffix):
    """
    Return the workspace path for a file-derived artifact.

    Parameters
    ----------
    filepath : pathlib.Path or str
        Source file path.
    suffix : str
        Artifact suffix appended to the source stem.

    Returns
    -------
    pathlib.Path
        Derived artifact path.
    """
    filepath = Path(filepath)
    return workspace_path(filepath.parent, f'{filepath.stem}{suffix}')
