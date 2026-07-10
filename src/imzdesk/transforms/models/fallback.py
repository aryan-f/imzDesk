from imzdesk.transforms.models.base import Model


class Fallback(Model):

    def __init__(self, *args, **kwargs):
        raise ImportError('Embedding models require the optional `torch` dependency. Install imzdesk with the `extras` group.')

    def embed(self, image):
        raise ImportError('Embedding models require the optional `torch` dependency. Install imzdesk with the `extras` group.')
