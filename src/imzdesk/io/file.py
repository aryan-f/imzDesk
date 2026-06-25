import abc
from typing import ClassVar


class BaseFileIO(abc.ABC):
    extensions: ClassVar[tuple[str, ...]]
