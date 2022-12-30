import io
import pathlib
from abc import ABC, abstractmethod
from typing import BinaryIO, Self


class FileFormat(ABC):
    @classmethod
    def sniff_bytes(cls, data: bytes) -> Self | None:
        with io.BytesIO(data) as f:
            return cls.sniff(f)

    @classmethod
    @abstractmethod
    def sniff(cls, f: BinaryIO) -> Self | None:
        pass

    @property
    @abstractmethod
    def suggested_extension(self) -> str:
        pass

    @abstractmethod
    def export(self, path: pathlib.Path, fmt: str = None) -> pathlib.Path:
        pass
