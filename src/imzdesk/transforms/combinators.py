from collections.abc import Callable, Sequence

import numpy as np

from imzdesk.transforms._random import WorkerRandomMixin
from imzdesk.transforms.base import Transform


class RandomApply(Transform, WorkerRandomMixin):
    """Apply a transform sequence with a sample-level probability."""

    def __init__(self, transforms: Sequence[Callable], p: float = 0.5, seed: int | None = None):
        if not 0 <= p <= 1:
            raise ValueError('Probability must be between zero and one.')
        self.transforms = list(transforms)
        self.p = p
        self._init_random(seed)

    def __call__(self, image):
        if self._rng().random() >= self.p:
            return image
        for transform in self.transforms:
            image = transform(image)
        return image


class RandomChoice(Transform, WorkerRandomMixin):
    """Apply one transform selected at sample level."""

    def __init__(
        self,
        transforms: Sequence[Callable],
        probabilities: Sequence[float] | None = None,
        seed: int | None = None,
    ):
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
        index = self._rng().choice(len(self.transforms), p=self.probabilities)
        return self.transforms[index](image)
