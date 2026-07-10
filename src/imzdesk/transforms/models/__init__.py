from .base import Model

try:
    import torch
except ImportError as error:
    from .fallback import Fallback as DreaMS
else:
    from .dreams import DreaMS


MODELS = {
    'roman-bushuiev/DreaMS': DreaMS,
}
