import abc


class Transform(abc.ABC):
    """
    Base class for transforms.
    """

    @abc.abstractmethod
    def __call__(self, image):
        pass
