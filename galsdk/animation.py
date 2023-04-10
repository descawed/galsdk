import struct
from pathlib import Path
from typing import BinaryIO, Iterable, Self

from galsdk import util
from galsdk.format import Archive


class AnimationDb(Archive[bytes]):
    SECTOR_SIZE = 0x800
    DEFAULT_HEADER = b'\0' * 0x48

    def __init__(self, animations: list[bytes] = None, header: bytes = DEFAULT_HEADER):
        self.header = header
        self.animations = animations or []

    @property
    def supports_nesting(self) -> bool:
        return False

    @property
    def suggested_extension(self) -> str:
        return '.ADB'

    def __getitem__(self, item: int) -> bytes:
        return self.animations[item]

    def __setitem__(self, key: int, value: bytes):
        self.animations[key] = value

    def __delitem__(self, key: int):
        del self.animations[key]

    def __len__(self) -> int:
        return len(self.animations)

    def __iter__(self) -> Iterable[bytes]:
        yield from self.animations

    def append(self, item: bytes):
        self.animations.append(item)

    def unpack_one(self, path: Path, index: int) -> Path:
        path.write_bytes(self.animations[index])
        return path

    @classmethod
    def import_explicit(cls, paths: Iterable[Path], fmt: str = None) -> Self:
        return cls([path.read_bytes() for path in paths])

    def export(self, path: Path, fmt: str = None) -> Path:
        path.mkdir(exist_ok=True)
        for i, animation in enumerate(self.animations):
            if animation or fmt == 'all':
                (path / f'{i:03}').write_bytes(animation)
        return path

    @classmethod
    def read(cls, f: BinaryIO, **kwargs) -> Self:
        directory = struct.unpack('<512I', util.read_exact(f, cls.SECTOR_SIZE))
        directory_len = len(directory)
        data_size = util.int_from_bytes(f.read(4))
        data = util.read_exact(f, data_size)
        header = data[:directory[1]]
        animations = []
        for i in range(0, directory_len, 2):
            size = directory[0]
            offset = directory[i + 1]
            if size == 0 and offset == 0:
                animations.append(b'')
            else:
                for j in range(i + 2, directory_len, 2):
                    next_offset = directory[j + 1]
                    if next_offset > 0:
                        animations.append(data[offset:next_offset])
                        break
                else:
                    animations.append(data[offset:])
        # we read the whole first sector as the directory, but there aren't that many entries, so delete all the dummy
        # empty entries we added at the end
        while not animations[-1]:
            del animations[-1]
        return cls(animations, header)

    def write(self, f: BinaryIO, **kwargs):
        total_size = 0
        offset = len(self.header)
        for animation in self.animations:
            size = len(animation)
            if size > 0:
                f.write(total_size.to_bytes(4, 'little'))
                f.write(offset.to_bytes(4, 'little'))
            else:
                f.write(b'\0\0\0\0\0\0\0\0')
            total_size += size
            offset += size
        bytes_remaining = self.SECTOR_SIZE - f.tell()
        if bytes_remaining < 0:
            raise ValueError('Too many animations')
        if bytes_remaining > 0:
            f.write(b'\0' * bytes_remaining)
        f.write(total_size.to_bytes(4, 'little'))
        f.write(self.header)
        for animation in self.animations:
            f.write(animation)


def pack_db(db: AnimationDb, files: Iterable[Path]):
    for path in files:
        if path.is_dir():
            pack_db(db, path.iterdir())
        else:
            db.append(path.read_bytes())


def unpack(db_path: Path, out_path: Path, unpack_all: bool):
    with db_path.open('rb') as f:
        db = AnimationDb.read(f)
    db.export(out_path, 'all' if unpack_all else None)


def pack(db_path: Path, in_paths: Iterable[Path]):
    db = AnimationDb()
    pack_db(db, in_paths)
    with db_path.open('wb') as f:
        db.write(f)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Pack and unpack Galerians animation databases')
    subparsers = parser.add_subparsers()

    pack_parser = subparsers.add_parser('pack', help='Create an animation database from a list of files')
    pack_parser.add_argument('db', help='Animation database to be created')
    pack_parser.add_argument('files', nargs='*', help='Files to be added to the database. If any paths are directories '
                             'they will be included recursively')
    pack_parser.set_defaults(action=lambda a: pack(Path(a.db), (Path(p) for p in a.files)))

    unpack_parser = subparsers.add_parser('unpack', help='Unpack files from an animation database')
    unpack_parser.add_argument('-a', '--all', help='Create a file for all indexes in the database, even ones which '
                               'are not populated. This will make repacking the database more convenient.',
                               action='store_true')
    unpack_parser.add_argument('db', help='Animation database to be unpacked')
    unpack_parser.add_argument('dir', help='Directory the files will be extracted to')
    unpack_parser.set_defaults(action=lambda a: unpack(Path(a.db), Path(a.dir), a.all))

    args = parser.parse_args()
    args.action(args)
