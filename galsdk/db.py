import math
import os
import os.path
from pathlib import Path
from typing import BinaryIO, Container, Iterable, Self

import galsdk.file as util
from galsdk.format import Archive


class Database(Archive[bytes]):
    """
    A packed database of game files

    This is the database format used by the game's .CDB files, as well as MODULE.BIN. Related files are packed together
    into a single CDB file. There are two variants - an "extended" form that records file sizes with byte precision,
    and a non-extended form that records file sizes with sector precision. The non-extended form will pad files with
    null bytes to the nearest sector boundary.
    """
    SECTOR_SIZE = 0x800

    def __init__(self, extended: bool = False):
        """
        Create a new file database

        :param extended: If True, file sizes will be recorded with byte precision. Otherwise, files will be padded with
            null bytes to the nearest sector boundary.
        """
        super().__init__()
        self.extended = extended
        self.files = []

    @property
    def suggested_extension(self) -> str:
        return '.CDB'

    @property
    def supports_nesting(self) -> bool:
        return False

    @property
    def metadata(self) -> dict[str, bool]:
        return {'extended': self.extended}

    @classmethod
    def from_metadata(cls, metadata: dict[str, bool | int | float | str | list | tuple | dict]) -> Self:
        return cls(metadata['extended'])

    @classmethod
    def import_explicit(cls, paths: Iterable[Path], fmt: str = None) -> Self:
        is_extended = fmt in ['extended', 'cdx', 'bin']
        db = cls(is_extended)
        for path in paths:
            db.append_file(path)
        return db

    def export(self, path: Path, fmt: str = None) -> Path:
        path.mkdir(exist_ok=True)
        for i, data in enumerate(self.files):
            with (path / f'{i:03}').open('wb') as f:
                f.write(data)
        return path

    def unpack_one(self, path: Path, index: int) -> Path:
        path.write_bytes(self.files[index])
        return path

    @classmethod
    def read(cls, f: BinaryIO, **kwargs) -> Self:
        """
        Read a database file from a given path

        :param f: Binary data stream to read the database file from
        """
        num_entries = util.int_from_bytes(f.read(2))
        extended = util.int_from_bytes(f.read(2)) != 0
        db = cls(extended)
        if extended:
            # skip over 4 dummy bytes
            f.seek(4, 1)
        directory = f.read((8 if extended else 4)*num_entries)
        i = 0
        while i < len(directory):
            start_sector = util.int_from_bytes(directory[i:i+2])
            num_sectors = util.int_from_bytes(directory[i+2:i+4])
            if extended:
                final_sector_len = util.int_from_bytes(directory[i+4:i+6])
                i += 8
            else:
                final_sector_len = cls.SECTOR_SIZE
                i += 4
            f.seek(start_sector*cls.SECTOR_SIZE)
            size = (num_sectors - 1)*cls.SECTOR_SIZE + final_sector_len
            db.append(util.read_some(f, size))

        return db

    def write(self, f: BinaryIO, **kwargs):
        """
        Write the files in this database to a single packed database file

        :param f: Binary data stream to write the database file to
        """
        f.write(len(self.files).to_bytes(2, 'little'))
        if self.extended:
            f.write(b'\x01\0\0\0\0\0')
        else:
            f.write(b'\0\0')

        current_sector = 1
        for data in self.files:
            f.write(current_sector.to_bytes(2, 'little'))
            sector_count = math.ceil(len(data)/self.SECTOR_SIZE)
            f.write(sector_count.to_bytes(2, 'little'))
            if self.extended:
                final_sector_len = len(data) % self.SECTOR_SIZE
                # this is actually a 16-bit value but the last two bytes of the directory entry are unused
                f.write(final_sector_len.to_bytes(4, 'little'))
            current_sector += sector_count

        bytes_remaining = self.SECTOR_SIZE - f.tell()
        if bytes_remaining < 0:
            raise OverflowError('Too many files')
        if f.readable():
            # if we're writing over an existing file, just seek ahead
            f.seek(bytes_remaining, os.SEEK_CUR)
        else:
            f.write(b'\0' * bytes_remaining)
        for data in self.files:
            f.write(data)
            bytes_over = len(data) % self.SECTOR_SIZE
            if bytes_over > 0:
                f.write(b'\0' * (self.SECTOR_SIZE - bytes_over))

    def __iter__(self) -> Iterable[bytes]:
        """Iterate over the files in the database"""
        yield from self.files

    def __getitem__(self, item: int) -> bytes:
        """Get the contents of the file in the database at the given index"""
        return self.files[item]

    def __setitem__(self, key: int, value: bytes):
        """Set the contents of the file in the database at the given index"""
        self.files[key] = value

    def __delitem__(self, key: int):
        """Deletes the file in the database at the given index. Note that this will re-number subsequent files."""
        del self.files[key]

    def __len__(self) -> int:
        """The number of files in the database"""
        return len(self.files)

    def append(self, data: bytes):
        """
        Append data to the database as a new file

        :param data: The data of the file to be added to the database
        """
        self.files.append(data)

    def insert(self, index: int, item: bytes):
        self.files.insert(index, item)

    def append_raw(self, item: bytes):
        return self.append(item)

    def append_file(self, path: Path):
        """
        Append a file to the database

        :param path: Path to the file to be added to the database
        """
        with path.open('rb') as f:
            self.append(f.read())


def pack_db(db: Database, files: Iterable[Path]):
    for path in files:
        if path.is_dir():
            pack_db(db, path.iterdir())
        else:
            db.append_file(path)


def pack(extended: bool, files: Iterable[Path], cdb: Path):
    db = Database(extended)
    pack_db(db, files)
    with cdb.open('wb') as f:
        db.write(f)


def unpack(cdb: str, target: str, indexes: Container[int] = None):
    with open(cdb, 'rb') as f:
        db = Database.read(f)
    for i, data in enumerate(db):
        if indexes and i not in indexes:
            continue
        output_path = os.path.join(target, f'{i:03}')
        with open(output_path, 'wb') as f:
            f.write(data)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Pack or unpack Galerians CDB files')
    subparsers = parser.add_subparsers(required=True)

    pack_parser = subparsers.add_parser('pack', help='Create a CDB from a list of files')
    pack_parser.add_argument('-x', '--extended',
                             help='Create an extended database that tracks file size with byte precision rather than '
                                  'sector precision', action='store_true')
    pack_parser.add_argument('cdb', help='Path to CDB to be created')
    pack_parser.add_argument('files', nargs='+', help='One or more files to include in the database. If the path is a '
                             'directory, it will be packed recursively.')
    pack_parser.set_defaults(action=lambda a: pack(a.extended, (Path(p) for p in a.files), Path(a.cdb)))

    unpack_parser = subparsers.add_parser('unpack', help='Unpack files from a CDB into a directory')
    unpack_parser.add_argument('cdb', help='Path to CDB to be unpacked')
    unpack_parser.add_argument('target', help='Path to directory where files will be unpacked')
    unpack_parser.add_argument('indexes', nargs='*', type=int, help='One or more indexes to extract from the database. '
                               'If not provided, all files in the database will be extracted')
    unpack_parser.set_defaults(action=lambda a: unpack(a.cdb, a.target, set(a.indexes)))

    args = parser.parse_args()
    args.action(args)
