from .base import ImageBase
from .msi import MSI
from .wsi import WSI

CLASSES = {
    'MSI': MSI,
    'WSI': WSI,
}
