from __future__ import annotations

import io
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, Generic, Iterable, Self, TypeVar

from galsdk.file import KeepReader


class FileFormat(ABC):
    @classmethod
    def sniff_bytes(cls, data: bytes) -> Self | None:
        with io.BytesIO(data) as f:
            return cls.sniff(f)

    @classmethod
    def sniff(cls, f: BinaryIO) -> Self | None:
        try:
            db = cls.read(f)
            return db
        except Exception:
            return None

    @property
    @abstractmethod
    def suggested_extension(self) -> str:
        pass

    @classmethod
    def read_bytes(cls, data: bytes, **kwargs) -> Self:
        with io.BytesIO(data) as f:
            return cls.read(f, **kwargs)

    @classmethod
    @abstractmethod
    def read(cls, f: BinaryIO, **kwargs) -> Self:
        pass

    @classmethod
    def read_with_raw(cls, f: BinaryIO, **kwargs) -> tuple[Self, bytes]:
        keeper = KeepReader(f)
        obj = cls.read(keeper, **kwargs)
        return obj, keeper.buffer

    @abstractmethod
    def write(self, f: BinaryIO, **kwargs):
        pass

    @classmethod
    @abstractmethod
    def import_(cls, path: Path, fmt: str = None) -> Self:
        pass

    @abstractmethod
    def export(self, path: Path, fmt: str = None) -> Path:
        pass


T = TypeVar('T')


class Archive(FileFormat, Generic[T]):
    def __init__(self, raw_data: bytes = None):
        self.raw_data = raw_data

    @property
    @abstractmethod
    def supports_nesting(self) -> bool:
        pass

    @property
    def is_ready(self) -> bool:
        """Is this archive ready to be unpacked?"""
        return True

    @property
    def metadata(self) -> dict[str, bool | int | float | str | list | tuple | dict]:
        return {}

    @classmethod
    def from_metadata(cls, _metadata: dict[str, bool | int | float | str | list | tuple | dict]) -> Self:
        return cls()

    @abstractmethod
    def __getitem__(self, item: int) -> T | Self:
        pass

    @abstractmethod
    def __setitem__(self, key: int, value: T | Self):
        pass

    @abstractmethod
    def __delitem__(self, key: int):
        pass

    @abstractmethod
    def __iter__(self) -> Iterable[T | Self]:
        pass

    @abstractmethod
    def __len__(self) -> int:
        pass

    @abstractmethod
    def append(self, item: T | Self):
        pass

    @abstractmethod
    def append_raw(self, item: bytes):
        pass

    @classmethod
    def read_save_raw(cls, f: BinaryIO, **kwargs) -> Self:
        obj, raw_data = cls.read_with_raw(f, **kwargs)
        obj.raw_data = raw_data
        return obj

    @classmethod
    def sniff(cls, f: BinaryIO) -> Self | None:
        try:
            return cls.read_save_raw(f)
        except Exception:
            return None

    def iter_flat(self) -> Iterable[T]:
        for item in self:
            if isinstance(item, Archive):
                yield from item.iter_flat()
            else:
                yield item

    @classmethod
    def import_(cls, path: Path, fmt: str = None) -> Self:
        if fmt is None:
            fmt = path.suffix or None
        return cls.import_explicit(path.iterdir(), fmt)

    @classmethod
    @abstractmethod
    def import_explicit(cls, paths: Iterable[Path], fmt: str = None) -> Self:
        pass

    @classmethod
    def pack(cls, path: Path, fmt: str = None):
        return cls.import_(path, fmt)

    @abstractmethod
    def unpack_one(self, path: Path, index: int) -> Path:
        pass

    def unpack(self, path: Path, recursive: bool = False):
        path.mkdir(exist_ok=True)
        for i, item in enumerate(self):
            sub_path = path / f'{i:03}'
            if recursive and isinstance(item, Archive):
                item.unpack(sub_path, recursive)
            else:
                self.unpack_one(sub_path, i)
