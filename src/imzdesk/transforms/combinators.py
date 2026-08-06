import numpy as np

from imzdesk.transforms._random import WorkerRandomMixin
from imzdesk.transforms.base import Transform


class RandomApply(Transform, WorkerRandomMixin):
    def __init__(self, transforms, p=0.5, seed=None):
        """
        Initialize probabilistic application of a transform sequence.

        Parameters
        ----------
        transforms : sequence of callable
            Transforms applied in order when the sample is selected.
        p : float, default=0.5
            Probability of applying the sequence.
        seed : int, optional
            Base random seed.
        """
        if not 0 <= p <= 1:
            raise ValueError('Probability must be between zero and one.')
        self.transforms = list(transforms)
        self.p = p
        self._init_random(seed)

    def __call__(self, image):
        """
        Apply the transform sequence to a randomly selected sample.
        """
        if self._rng().random() >= self.p:
            return image
        for transform in self.transforms:
            image = transform(image)
        return image


class RandomChoice(Transform, WorkerRandomMixin):
    def __init__(
        self,
        transforms,
        probabilities=None,
        seed=None,
    ):
        """
        Initialize random selection from a transform sequence.

        Parameters
        ----------
        transforms : sequence of callable
            Candidate transforms.
        probabilities : sequence of float, optional
            Selection probability for each transform. The uniform
            distribution is used when omitted.
        seed : int, optional
            Base random seed.
        """
        self.transforms = list(transforms)
        if not self.transforms:
            raise ValueError('RandomChoice requires at least one transform.')
        if probabilities is None:
            self.probabilities = None
        else:
            probabilities = np.asarray(probabilities, dtype=np.float64)
            if len(probabilities) != len(self.transforms):
                raise ValueError('Probabilities must match the number of transforms.')
            if np.any(probabilities < 0) or not np.isclose(probabilities.sum(), 1):
                raise ValueError('Probabilities must be nonnegative and sum to one.')
            self.probabilities = probabilities
        self._init_random(seed)

    def __call__(self, image):
        """
        Apply one randomly selected transform to a sample.
        """
        index = self._rng().choice(len(self.transforms), p=self.probabilities)
        return self.transforms[index](image)
