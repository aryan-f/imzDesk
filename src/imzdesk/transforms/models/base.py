import abc

from imzdesk.core.data import RImage, DImage


class Model(abc.ABC):
    """
    Embedding model base class.
    """

    @abc.abstractmethod
    def embed(self, image: RImage) -> DImage:
        pass
