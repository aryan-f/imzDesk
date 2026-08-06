import numpy as np


class WorkerRandomMixin:
    """
    Worker-aware NumPy random generator for stochastic transforms.
    """

    def _init_random(self, seed):
        """
        Initialize worker-local random state.

        Parameters
        ----------
        seed : int, optional
            Base random seed.
        """
        self.seed = seed
        self._generator = None
        self._worker_id = None

    def _rng(self):
        """
        Return the random generator for the current data-loader worker.
        """
        try:
            from torch.utils.data import get_worker_info
            worker = get_worker_info()
        except ImportError:
            worker = None
        worker_id = None if worker is None else worker.id
        if self._generator is None or worker_id != self._worker_id:
            seed = self.seed
            if worker is not None:
                seed = worker.seed if seed is None else np.random.SeedSequence([seed, worker.id])
            self._generator = np.random.default_rng(seed)
            self._worker_id = worker_id
        return self._generator
