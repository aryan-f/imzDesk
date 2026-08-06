import abc


class Model(abc.ABC):
    """
    Embedding model base class.
    """

    @abc.abstractmethod
    def embed(self, image):
        """
        Embed the spectra in a ragged image into dense vectors.

        Parameters
        ----------
        image : imzdesk.core.RImage
            Ragged spectra to embed.

        Returns
        -------
        imzdesk.core.DImage
            Dense embedding vectors and source coordinates.
        """
        pass
