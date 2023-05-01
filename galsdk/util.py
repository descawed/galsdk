import shutil
from pathlib import Path
from typing import BinaryIO, Literal, TextIO, overload

import numpy as np


def int_from_bytes(b: bytes, endianness: Literal['little', 'big'] = 'little', *, signed: bool = False):
    if b == b'':
        raise ValueError('Attempted to read int from empty bytes')
    return int.from_bytes(b, endianness, signed=signed)


def interpolate(amount: float, p1: np.ndarray, p2: np.ndarray) -> np.ndarray:
    return p1 + (p2 - p1) * amount


def scale_to_fit(original_width: int, original_height: int, available_width: int, available_height: int,
                 max_scale: int) -> tuple[int, int]:
    if original_width > original_height:
        new_width = min(available_width, original_width * max_scale)
        new_height = original_height * (new_width / original_width)
    else:
        new_height = min(available_height, original_height * max_scale)
        new_width = original_width * (new_height / original_height)

    return int(new_width), int(new_height)


def quat_mul(q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
        """Multiply two quaternions which are in XYZW order"""
        x1, y1, z1, w1 = q1
        x2, y2, z2, w2 = q2

        return np.array([
            w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2,
            w1*z2 + x1*y2 - y1*x2 + z1*w2,
            w1*w2 - x1*x2 - y1*y2 - z1*z2,
        ], np.float32)


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


def panda_path(path: Path) -> str:
    if drive := path.drive:
        # panda requires a Unix-style path
        path_str = path.as_posix()[len(drive):]
        # TODO: check if this works with UNC paths
        clean_drive = drive.replace(':', '').replace('\\', '/').lower()
        return f'/{clean_drive}{path_str}'
    else:
        return str(path)
