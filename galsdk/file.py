import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import BinaryIO, Literal, TextIO, overload


class KeepReader(BinaryIO):
    """
    A BinaryIO stream that keeps a copy of the data read, in the same order as the original file
    """

    def __init__(self, source: BinaryIO):
        self.source = source
        self.start = source.tell()  # we have to have this for absolute seeks to work
        self.current = 0
        self.buf = bytearray()

    def _add_data(self, data: bytes):
        end = self.current + len(data)
        # because of the possibility of seeking, we won't always be appending at the end
        if end > len(self.buf):
            self.buf.extend(bytes(end - len(self.buf)))
        self.buf[self.current:end] = data
        self.current = end

    @property
    def buffer(self) -> bytes:
        return bytes(self.buf)

    def __enter__(self):
        self.source.__enter__()

    def close(self):
        self.source.close()

    def fileno(self):
        return self.source.fileno()

    def flush(self):
        self.source.flush()

    def isatty(self):
        return self.source.isatty()

    def read(self, __n=-1):
        data = self.source.read(__n)
        self._add_data(data)
        return data

    def readable(self):
        return self.source.readable()

    def readline(self, __limit=-1):
        data = self.source.readline(__limit)
        self._add_data(data)
        return data

    def readlines(self, __hint=-1):
        data = self.source.readlines(__hint)
        for line in data:
            self._add_data(line)
        return data

    def seek(self, __offset, __whence=os.SEEK_SET):
        abs_offset = self.source.seek(__offset, __whence)
        rel_offset = abs_offset - self.start
        if rel_offset < 0:
            raise EOFError('KeepReader sought to before the start of the buffer')
        if rel_offset > self.current:
            # reset to before the seek and read the data that was skipped
            self.source.seek(self.start + self.current)
            self.read(rel_offset - self.current)
        else:
            self.current = rel_offset
        return abs_offset

    def seekable(self):
        return self.source.seekable()

    def tell(self):
        return self.source.tell()

    def truncate(self, __size=None):
        return self.source.truncate(__size)

    def writable(self):
        return self.source.writable()

    def write(self, __s):
        return self.source.write(__s)

    def writelines(self, __lines):
        self.source.writelines(__lines)

    def __next__(self):
        return self.source.__next__()

    def __iter__(self):
        return self.source.__iter__()

    def __exit__(self, __t, __value, __traceback):
        return self.source.__exit__(__t, __value, __traceback)


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


def panda_path(path: Path) -> str:
    if drive := path.drive:
        # panda requires a Unix-style path
        path_str = path.as_posix()[len(drive):]
        # TODO: check if this works with UNC paths
        clean_drive = drive.replace(':', '').replace('\\', '/').lower()
        return f'/{clean_drive}{path_str}'
    else:
        return str(path)


def show_dir(path: Path):
    if not path.is_dir():
        raise NotADirectoryError(f'{path} is not a directory')

    match platform.system():
        case 'Windows':
            os.startfile(path)
        case 'Darwin':
            subprocess.run(['open', path])
        case _:
            subprocess.run(['xdg-open', path])
