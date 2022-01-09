import math
import os.path

from typing import Container, Iterable


class Database:
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
        self.extended = extended
        self.files = []

    def read(self, path: str):
        """
        Read a database file from a given path

        :param path: Path to the database file
        """
        self.files = []
        with open(path, 'rb') as f:
            num_entries = int.from_bytes(f.read(2), 'little')
            self.extended = int.from_bytes(f.read(2), 'little') != 0
            if self.extended:
                # skip over 4 dummy bytes
                f.seek(4, 1)
            directory = f.read((8 if self.extended else 4)*num_entries)
            i = 0
            while i < len(directory):
                start_sector = int.from_bytes(directory[i:i+2], 'little')
                num_sectors = int.from_bytes(directory[i+2:i+4], 'little')
                if self.extended:
                    final_sector_len = int.from_bytes(directory[i+4:i+6], 'little')
                    i += 8
                else:
                    final_sector_len = self.SECTOR_SIZE
                    i += 4
                f.seek(start_sector*self.SECTOR_SIZE)
                size = (num_sectors - 1)*self.SECTOR_SIZE + final_sector_len
                self.append(f.read(size))

    def write(self, path: str):
        """
        Write the files in this database to a single packed database file

        :param path: Path to the database file to be written
        """
        with open(path, 'wb') as f:
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
            f.write(b'\0' * bytes_remaining)
            for data in self.files:
                f.write(data)
                bytes_remaining = self.SECTOR_SIZE - (len(data) % self.SECTOR_SIZE)
                f.write(b'\0' * bytes_remaining)

    def __iter__(self) -> Iterable[bytes]:
        """Iterate over the files in the database"""
        yield from self.files

    def __getitem__(self, item: int) -> bytes:
        """Get the contents of the file in the database at the given index"""
        return self.files[item]

    def __setitem__(self, key: int, value: bytes):
        """Set the contents of the file in the database at the given index"""
        self.files[key] = value

    def __len__(self) -> int:
        """The number of files in the database"""
        return len(self.files)

    def append(self, data: bytes):
        """
        Append data to the database as a new file

        :param data: The data of the file to be aded to the database
        """
        self.files.append(data)

    def append_file(self, path: str):
        """
        Append a file to the database

        :param path: Path to the file to be added to the database
        """
        with open(path, 'rb') as f:
            self.append(f.read())


def pack(extended: bool, files: Iterable[str], cdb: str):
    db = Database(extended)
    for path in files:
        db.append_file(path)
    db.write(cdb)


def unpack(cdb: str, target: str, indexes: Container[int] = None):
    db = Database()
    db.read(cdb)
    for i, data in enumerate(db):
        if indexes is not None and i not in indexes:
            continue
        output_path = os.path.join(target, str(i))
        with open(output_path, 'wb') as f:
            f.write(data)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Pack or unpack Galerians CDB files')
    subparsers = parser.add_subparsers()

    pack_parser = subparsers.add_parser('pack', help='Create a CDB from a list of files')
    pack_parser.add_argument('-x', '--extended',
                             help='Create an extended database that tracks file size with byte precision rather than '
                                  'sector precision', action='store_true')
    pack_parser.add_argument('cdb', help='Path to CDB to be created')
    pack_parser.add_argument('files', nargs='+', help='One or more files to include in the database')
    pack_parser.set_defaults(action=lambda a: pack(a.extended, a.files, a.cdb))

    unpack_parser = subparsers.add_parser('unpack', help='Unpack files from a CDB into a directory')
    unpack_parser.add_argument('cdb', help='Path to CDB to be unpacked')
    unpack_parser.add_argument('target', help='Path to directory where files will be unpacked')
    unpack_parser.add_argument('indexes', nargs='*', type=int, help='One or more indexes to extract from the database. '
                               'If not provided, all files in the database will be extracted')
    unpack_parser.set_defaults(action=lambda a: unpack(a.cdb, a.target, set(a.indexes)))

    args = parser.parse_args()
    args.action(args)
