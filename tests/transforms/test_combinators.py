import builtins
from types import SimpleNamespace

import numpy as np
import pytest

import imzdesk.transforms as T
from imzdesk.core import PairedImage, Transform


def test_random_apply_runs_all_operations_in_order():
    transform = T.RandomApply([
        lambda value: value + 2,
        lambda value: value * 3,
    ], p=1, seed=0)

    assert transform(4) == 18


def test_random_apply_probability_zero_returns_same_object():
    image = np.ones((2, 2))

    result = T.RandomApply([lambda value: value + 1], p=0, seed=0)(image)

    assert result is image


def test_random_apply_passes_pair_as_one_sample():
    pair = PairedImage(np.array([1]), np.array([2]), Transform.identity())

    result = T.RandomApply([
        lambda sample: PairedImage(sample.wsi + 1, sample.msi + 1, sample.registration),
    ], p=1, seed=0)(pair)

    np.testing.assert_array_equal(result.wsi, [2])
    np.testing.assert_array_equal(result.msi, [3])


def test_random_choice_honors_probabilities():
    transform = T.RandomChoice(
        [lambda value: value + 1, lambda value: value + 10],
        probabilities=[0, 1],
        seed=0,
    )

    assert transform(5) == 15


def test_random_choice_is_reproducible_for_seed():
    operations = [lambda _: 0, lambda _: 1, lambda _: 2]
    first = T.RandomChoice(operations, seed=12)
    second = T.RandomChoice(operations, seed=12)

    assert [first(None) for _ in range(10)] == [second(None) for _ in range(10)]


def test_random_transform_reseeds_for_worker(monkeypatch):
    worker = SimpleNamespace(id=2, seed=999)
    monkeypatch.setattr('torch.utils.data.get_worker_info', lambda: worker)
    transform = T.RandomApply([], p=0.5, seed=7)
    expected = np.random.default_rng(np.random.SeedSequence([7, worker.id]))

    assert transform._rng().uniform() == expected.uniform()


def test_random_transform_works_without_torch(monkeypatch):
    original_import = builtins.__import__

    def reject_torch_data(name, *args, **kwargs):
        if name == 'torch.utils.data':
            raise ImportError
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', reject_torch_data)
    transform = T.RandomApply([lambda value: value + 1], p=1, seed=2)

    assert transform(1) == 2


@pytest.mark.parametrize('constructor', [
    lambda: T.RandomApply([], p=-1),
    lambda: T.RandomChoice([]),
    lambda: T.RandomChoice([lambda value: value], probabilities=[0.5, 0.5]),
    lambda: T.RandomChoice([lambda value: value], probabilities=[-1]),
    lambda: T.RandomChoice([lambda value: value], probabilities=[0.5]),
])
def test_random_combinators_validate_parameters(constructor):
    with pytest.raises(ValueError):
        constructor()
