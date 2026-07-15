import pytest

from imzdesk.transforms.models.fallback import Fallback


def test_fallback_raises_import_error_on_instantiation():
    with pytest.raises(ImportError, match='torch'):
        Fallback()
