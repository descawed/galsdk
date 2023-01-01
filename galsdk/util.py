import shutil
from pathlib import Path
from typing import BinaryIO, Literal, TextIO, overload


def int_from_bytes(b: bytes, endianness: Literal['little', 'big'] = 'little', *, signed: bool = False):
    if b == b'':
        raise ValueError('Attempted to read int from empty bytes')
    return int.from_bytes(b, endianness, signed=signed)


@overload
def read_exact(f: BinaryIO, size: int) -> bytes:
    pass


@overload
def read_exact(f: TextIO, size: int) -> str:
    pass


def read_exact(f: BinaryIO | TextIO, size: int) -> bytes | str:
    data = f.read(size)
    if len(data) < size:
        raise EOFError(f'EOF encountered when attempting to read {size} bytes')
    return data


@overload
def read_some(f: BinaryIO, size: int) -> bytes:
    pass


@overload
def read_some(f: TextIO, size: int) -> str:
    pass


def read_some(f: BinaryIO | TextIO, size: int) -> bytes | str:
    data = f.read(size)
    if len(data) == 0 and size != 0:
        raise EOFError(f'EOF encountered when attempting to read {size} bytes')
    return data


def unlink(path: Path):
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink(True)
