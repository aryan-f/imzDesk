import logging

from .base import Model

logger = logging.getLogger(__name__)

try:
    import torch
except ImportError as error:
    logger.warning('Could not import torch. Embedding models will not be available.')
    from .fallback import Fallback as DreaMS
else:
    from .dreams import DreaMS


MODELS = {
    'roman-bushuiev/DreaMS': DreaMS,
}
