import pytest
from pydantic import ValidationError

from imzdesk.server.schema.images.msi import ReductionSettings


@pytest.mark.parametrize('scaling', ['robust', 'zscore'])
def test_nmf_requires_nonnegative_minmax_scaling(scaling):
    with pytest.raises(ValidationError, match='NMF requires min-max scaling'):
        ReductionSettings(method='nmf', scaling=scaling)


def test_nmf_accepts_minmax_scaling():
    settings = ReductionSettings(method='nmf', scaling='minmax')

    assert settings.scaling == 'minmax'
