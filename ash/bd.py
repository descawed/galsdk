from __future__ import annotations

import argparse
import sys

from pathlib import Path
from typing import BinaryIO, Iterable


class Bd1Archive:
    MAGIC = b'BD1\x01'

    def __init__(self, header_size: int = 0x40, entries: list[bytes] = None):
        self.header_size = header_size
        self.entries = entries or []

    @classmethod
    def read(cls, f: BinaryIO) -> Bd1Archive:
        start = f.tell()
        magic = f.read(4)
        if magic != cls.MAGIC:
            raise ValueError('Not a BD1 archive')

        f.seek(12, 1)
        num_entries = int.from_bytes(f.read(4), 'little')
        directory = [(int.from_bytes(f.read(4), 'little'), int.from_bytes(f.read(4), 'little') & 0xffffff)
                     for _ in range(num_entries)]
        directory.sort(key=lambda e: e[0])
        header_size = directory[0][0]
        entries = []
        for offset, length in directory:
            f.seek(start + offset)
            entries.append(f.read(length))

        return cls(header_size, entries)

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self) -> Iterable[bytes]:
        yield from self.entries

    def __getitem__(self, item: int) -> bytes:
        return self.entries[item]


class Bd2Archive:
    def __init__(self, sub_archives: list[Bd1Archive] = None):
        self.sub_archives = sub_archives or []

    @classmethod
    def read(cls, f: BinaryIO) -> Bd2Archive:
        sub_archives = []
        while True:
            magic = f.read(4)
            if len(magic) < 4:
                break

            if magic == Bd1Archive.MAGIC:
                f.seek(-4, 1)
                sub_archives.append(Bd1Archive.read(f))

        return cls(sub_archives)

    def __len__(self) -> int:
        return len(self.sub_archives)

    def __iter__(self) -> Iterable[Bd1Archive]:
        yield from self.sub_archives

    def __getitem__(self, item: int) -> Bd1Archive:
        return self.sub_archives[item]


def unpack(archive_path: Path, destination_path: Path):
    with archive_path.open('rb') as f:
        archive = Bd2Archive.read(f)

    if len(archive) == 0:
        print('Not a BD1 or BD2 archive', file=sys.stderr)
        return

    destination_path.mkdir(exist_ok=True)
    for i, sub_archive in enumerate(archive):
        if len(archive) == 1:
            path = destination_path
        else:
            path = destination_path / str(i)
            path.mkdir(exist_ok=True)

        for j, data in enumerate(sub_archive):
            data_path = path / str(j)
            data_path.write_bytes(data)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Unpack Galerians: Ash .bd1 and .bd2 archives')
    parser.add_argument('archive', type=Path, help='Archive file to unpack')
    parser.add_argument('dest', type=Path, help='Directory to unpack to. Defaults to archive path with no extension',
                        nargs='?')

    args = parser.parse_args()
    dest = args.dest
    if dest is None:
        dest = args.archive.with_suffix('')
    unpack(args.archive, dest)
