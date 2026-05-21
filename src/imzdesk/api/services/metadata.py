import aiofiles
import aiofiles.os
import yaml
from fastapi import HTTPException

from ..utils import get_metadata_path


async def read(target):
    """
    Reads the metadata file for a given target.

    If the file does not exist, an empty dictionary is returned.

    Parameters
    ----------
    target: Path
        The path to the target.

    Raises
    ------
    HTTPException(422)
        If the metadata file is not a valid YAML mapping.

    Returns
    -------
    dict
        The metadata as a dictionary.
    """
    metadata = get_metadata_path(target)

    if await aiofiles.os.path.exists(metadata):
        async with aiofiles.open(metadata, 'r') as file:
            data = yaml.safe_load(await file.read()) or {}
    else:
        data = {}

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=422,
            detail='Metadata YAML must contain a flat mapping.',
        )

    return data


async def write(target, data):
    """
    Writes the metadata file for a given target.

    Parameters
    ----------
    target: Path
        The path to the target.
    data: dict
        The metadata to be written.
    """
    metadata = get_metadata_path(target)

    async with aiofiles.open(metadata, 'w') as file:
        string = yaml.safe_dump(
            data,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )
        await file.write(string)
