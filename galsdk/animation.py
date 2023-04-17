from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntFlag
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Iterable, Self, Sequence

from galsdk import util
from galsdk.format import Archive, FileFormat


class AnimationFlag(IntFlag):
    UNKNOWN_0 = 1
    UNKNOWN_1 = 2
    UNKNOWN_2 = 4
    UNKNOWN_3 = 8
    UNKNOWN_4 = 0x10
    UNKNOWN_5 = 0x20
    UNKNOWN_6 = 0x40
    UNKNOWN_7 = 0x80
    UNKNOWN_8 = 0x100
    UNKNOWN_9 = 0x200
    UNKNOWN_10 = 0x400
    UNKNOWN_11 = 0x800
    UNKNOWN_12 = 0x1000
    UNKNOWN_13 = 0x2000
    UNKNOWN_14 = 0x4000
    UNKNOWN_15 = 0x8000
    UNKNOWN_16 = 0x10000
    UNKNOWN_17 = 0x20000
    UNKNOWN_18 = 0x40000
    UNKNOWN_19 = 0x80000
    UNKNOWN_20 = 0x100000
    UNKNOWN_21 = 0x200000
    UNKNOWN_22 = 0x400000
    UNKNOWN_23 = 0x800000
    UNKNOWN_24 = 0x1000000
    UNKNOWN_25 = 0x2000000
    UNKNOWN_26 = 0x4000000
    UNKNOWN_27 = 0x8000000
    UNKNOWN_28 = 0x10000000
    FORWARD = 0x20000000
    TOGGLE_DIRECTION = 0x40000000
    END = 0x80000000


@dataclass
class Frame:
    translation: tuple[int, int, int]
    rotations: list[tuple[int, int, int]]
    flags: AnimationFlag
    
    @classmethod
    def from_raw(cls, values: Sequence[int]) -> Frame:
        translation = (values[0], values[1], values[2])
        rotations = []
        for i in range(3, len(values) - 1, 3):
            rotations.append((values[i], values[i + 1], values[i + 2]))
        return cls(translation, rotations, AnimationFlag(values[-1]))

    def to_raw(self) -> list[int]:
        raw = [*self.translation]
        for rotation in self.rotations:
            raw.extend(rotation)
        raw.append(self.flags)
        return raw


class Animation(FileFormat):
    def __init__(self, frames: list[Frame]):
        self.frames = frames

    @property
    def suggested_extension(self) -> str:
        return '.ANI'

    @classmethod
    def read(cls, f: BinaryIO, **kwargs) -> Self:
        prev_values = struct.unpack('<48hI', f.read(100))
        frames = [Frame.from_raw(prev_values)]

        # remaining frames are differential
        while not frames[-1].flags & AnimationFlag.END:
            values = []
            for i in range(48):
                byte = int.from_bytes(f.read(1), 'little', signed=True)
                if byte & 1:
                    second = f.read(1)[0]
                    values.append(second | ((byte >> 1) << 8))
                else:
                    values.append(prev_values[i] - (byte >> 1))
            values.append(int.from_bytes(f.read(4), 'little'))
            frames.append(Frame.from_raw(values))
            prev_values = values

        return cls(frames)

    def write(self, f: BinaryIO, **kwargs):
        prev_values = self.frames[0].to_raw()
        f.write(struct.pack('<48hI', *prev_values))

        for frame in self.frames[1:]:
            values = frame.to_raw()
            for i, value in enumerate(values[:-1]):
                diff = prev_values[i] - value
                if -64 <= diff <= 63:
                    f.write((diff << 1).to_bytes(1, 'little', signed=True))
                else:
                    f.write(((value << 1) | 0x100).to_bytes(2, 'big', signed=True))
            f.write(values[-1].to_bytes(4, 'little'))
            prev_values = values

    @classmethod
    def import_(cls, path: Path, fmt: str = None) -> Self:
        raise NotImplementedError

    def export(self, path: Path, fmt: str = None) -> Path:
        raise NotImplementedError


class AnimationDb(Archive[Animation | None]):
    SECTOR_SIZE = 0x800
    DEFAULT_HEADER = b'\0' * 0x48

    def __init__(self, animations: list[Animation | None] = None, header: bytes = DEFAULT_HEADER):
        self.header = header
        self.animations = animations or []

    @property
    def supports_nesting(self) -> bool:
        return False

    @property
    def suggested_extension(self) -> str:
        return '.ADB'

    def __getitem__(self, item: int) -> Animation | None:
        return self.animations[item]

    def __setitem__(self, key: int, value: Animation | None):
        self.animations[key] = value

    def __delitem__(self, key: int):
        del self.animations[key]

    def __len__(self) -> int:
        return len(self.animations)

    def __iter__(self) -> Iterable[Animation | None]:
        yield from self.animations

    def append(self, item: Animation | None):
        self.animations.append(item)

    def unpack_one(self, path: Path, index: int) -> Path:
        if animation := self.animations[index]:
            with path.open('wb') as f:
                animation.write(f)
        else:
            path.write_bytes(b'')
        return path

    @classmethod
    def import_explicit(cls, paths: Iterable[Path], fmt: str = None) -> Self:
        animations = []
        for path in paths:
            with path.open('rb') as f:
                animations.append(Animation.read(f))
        return cls(animations)

    def export(self, path: Path, fmt: str = None) -> Path:
        path.mkdir(exist_ok=True)
        for i, animation in enumerate(self.animations):
            sub_path = (path / f'{i:03}')
            if animation:
                with sub_path.open('wb') as f:
                    animation.write(f)
            elif fmt == 'all':
                sub_path.write_bytes(b'')
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
            size = directory[i]
            offset = directory[i + 1]
            if size == 0 and offset == 0:
                animations.append(None)
            else:
                for j in range(i + 2, directory_len, 2):
                    next_offset = directory[j + 1]
                    if next_offset > 0:
                        with BytesIO(data[offset:next_offset]) as buf:
                            animations.append(Animation.read(buf))
                        break
                else:
                    with BytesIO(data[offset:]) as buf:
                        animations.append(Animation.read(buf))
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
            if animation:
                animation.write(f)


def pack_db(db: AnimationDb, files: Iterable[Path]):
    for path in files:
        if path.is_dir():
            pack_db(db, path.iterdir())
        else:
            with path.open('rb') as f:
                db.append(Animation.read(f))


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
