import hashlib
import json
import logging

from imzdesk.io import ImageBase

logger = logging.getLogger(__name__)


def cache_path(image, suffix, key=None):
    """
    Derives the path for a cache file.

    Parameters
    ----------
    image: ImageBase
        The source image.
    suffix: str
        The suffix of the cache file.
    key: BaseModel, optional
        Used to generate a unique key for the cache file.

    Returns
    -------
    filepath: pathlib.Path
        The path to the cache file.
    """
    source = getattr(image, 'filepath', '<unknown>')
    if key is not None:
        payload = key.model_dump(mode='json')
        canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        hashed = hashlib.sha256(canonical).hexdigest()
        suffix = f'.{hashed}{suffix}'
        logger.debug('Derived keyed cache path source=%s key_hash=%s suffix=%s', source, hashed, suffix)
    path = image.derived_path(suffix)
    logger.debug('Resolved cache path source=%s path=%s', source, path)
    return path
