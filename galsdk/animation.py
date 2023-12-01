from __future__ import annotations

import functools
import io
import os
import struct
from dataclasses import astuple, dataclass
from enum import IntFlag
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Iterable, Self, Sequence

import numpy as np

from galsdk import file
from galsdk.coords import Dimension
from galsdk.format import Archive, FileFormat


class AnimationFlag(IntFlag):
    FLIP_HIT_SEGMENTS = 1
    SEGMENT_1_HIT = 2
    SEGMENT_2_HIT = 4
    SEGMENT_3_HIT = 8
    SEGMENT_4_HIT = 0x10
    SEGMENT_5_HIT = 0x20
    SEGMENT_6_HIT = 0x40
    SEGMENT_7_HIT = 0x80
    SEGMENT_8_HIT = 0x100
    SEGMENT_9_HIT = 0x200
    SEGMENT_10_HIT = 0x400
    SEGMENT_11_HIT = 0x800
    SEGMENT_12_HIT = 0x1000
    SEGMENT_13_HIT = 0x2000
    SEGMENT_14_HIT = 0x4000
    SEGMENT_15_HIT = 0x8000
    UNKNOWN_16 = 0x10000
    UNKNOWN_17 = 0x20000
    UNKNOWN_18 = 0x40000
    FACE_TARGET = 0x80000
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

    @property
    def hit_segment(self) -> int:
        flags = self
        if flags & self.FLIP_HIT_SEGMENTS:
            # flips the bit order from 0123456789ABCDEF to 3450129AB678CDEF
            flags = (flags << 3) & 0xe380 | flags & 0xf | (flags >> 3) & 0x1c70
        if flags & self.SEGMENT_1_HIT:
            return 1
        if flags & self.SEGMENT_2_HIT:
            return 2
        if flags & self.SEGMENT_3_HIT:
            return 3
        if flags & self.SEGMENT_4_HIT:
            return 4
        if flags & self.SEGMENT_5_HIT:
            return 5
        if flags & self.SEGMENT_6_HIT:
            return 6
        if flags & self.SEGMENT_7_HIT:
            return 7
        if flags & self.SEGMENT_8_HIT:
            return 8
        if flags & self.SEGMENT_9_HIT:
            return 9
        if flags & self.SEGMENT_10_HIT:
            return 10
        if flags & self.SEGMENT_11_HIT:
            return 11
        if flags & self.SEGMENT_12_HIT:
            return 12
        if flags & self.SEGMENT_13_HIT:
            return 13
        if flags & self.SEGMENT_14_HIT:
            return 14
        if flags & self.SEGMENT_15_HIT:
            return 15
        return 0


@dataclass
class AttackData:
    unknown1: int
    hit_angle: int
    unknown2: int
    damage: int
    type: int
    unknown3: int
    unknown4: int

    @property
    def is_empty(self) -> bool:
        return (self.unknown1 == 0 and self.hit_angle == 0 and self.unknown2 == 0 and self.damage == 0
                and self.type == 0 and self.unknown3 == 0 and self.unknown4 == 0)


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
    FRAME_TIME = 1 / 30
    DEFAULT_HEADER_SIZE = 72
    ATTACK_DATA_FORMAT = '<4h2bh'
    ATTACK_DATA_SIZE = struct.calcsize(ATTACK_DATA_FORMAT)
    NUM_ROTATIONS = 16

    def __init__(self, frames: list[Frame], name: str = None, attack_data: list[AttackData] = None):
        self.frames = frames
        self.name = name
        self.attack_data = attack_data or []

    @property
    def is_attack(self) -> bool:
        return not all(data.is_empty for data in self.attack_data)

    @property
    def header_len(self) -> int:
        return len(self.attack_data) * self.ATTACK_DATA_SIZE

    @functools.cache
    def convert_frame(self, i: int) -> tuple[np.ndarray, list[np.ndarray]]:
        frame = self.frames[i]
        translation = np.array(frame.translation, np.float32) / Dimension.SCALE_FACTOR
        rotations = []
        for j, raw_rotation in enumerate(frame.rotations):
            rotation = 360 * np.array(raw_rotation, np.float32) / 4096

            # special logic for lower body and shoulders
            # FIXME: in at least one case, the game applies this logic only for j == 0
            if i > 0 and j in [0, 3, 6]:
                last_rot = 360 * np.array(self.frames[i - 1].rotations[j], np.float32) / 4096
                diff = rotation - last_rot
                adj_x = rotation[0] + 180
                adj_y = 180 - rotation[1]
                adj_z = rotation[2] + 180
                if abs(adj_x - last_rot[0]) + abs(adj_z - last_rot[2]) < abs(diff[0]) + abs(diff[2]):
                    rotation = np.array([adj_x, adj_y, adj_z], np.float32)

            rotations.append(np.deg2rad(rotation))

        return translation, rotations

    @property
    def suggested_extension(self) -> str:
        return '.ANI'

    @classmethod
    def read(cls, f: BinaryIO, *, header_size: int = DEFAULT_HEADER_SIZE, **kwargs) -> Self:
        start = f.tell()
        end = f.seek(0, os.SEEK_END)
        f.seek(start)
        header = f.read(header_size)
        attack_data = []
        for i in range(0, header_size, cls.ATTACK_DATA_SIZE):
            attack_data.append(AttackData(*struct.unpack_from(cls.ATTACK_DATA_FORMAT, header, i)))

        prev_values = struct.unpack('<48hI', f.read(100))
        frames = [Frame.from_raw(prev_values)]

        # remaining frames are differential
        while not frames[-1].flags & AnimationFlag.END and f.tell() < end:
            values = []
            for i in range(cls.NUM_ROTATIONS * 3):
                byte = int.from_bytes(f.read(1), 'little', signed=True)
                if byte & 1:
                    second = f.read(1)[0]
                    values.append(second | ((byte >> 1) << 8))
                else:
                    values.append(prev_values[i] - (byte >> 1))
            values.append(int.from_bytes(f.read(4), 'little'))
            frames.append(Frame.from_raw(values))
            prev_values = values

        return cls(frames, attack_data=attack_data)

    def write(self, f: BinaryIO, **kwargs):
        for attack_data in self.attack_data:
            f.write(struct.pack(self.ATTACK_DATA_FORMAT, *astuple(attack_data)))

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

        # pad length to multiple of 4
        offset = f.tell()
        bytes_over = offset % 4
        if bytes_over > 0:
            f.write(bytes(4 - bytes_over))

    @classmethod
    def import_(cls, path: Path, fmt: str = None) -> Self:
        raise NotImplementedError

    def export(self, path: Path, fmt: str = None) -> Path:
        raise NotImplementedError


class AnimationDb(Archive[Animation | None]):
    SECTOR_SIZE = 0x800

    def __init__(self, animations: list[Animation | None] = None):
        super().__init__()
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

    def append_raw(self, item: bytes):
        with io.BytesIO(item) as f:
            self.append(Animation.read(f))

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
        directory = struct.unpack('<512I', file.read_exact(f, cls.SECTOR_SIZE))
        directory_len = len(directory)
        data_size = file.int_from_bytes(f.read(4))
        data = file.read_exact(f, data_size)
        animations = []
        for i in range(0, directory_len, 2):
            header_offset = directory[i]
            data_offset = directory[i + 1]
            header_size = data_offset - header_offset
            if header_offset == 0 and data_offset == 0:
                animations.append(None)
            else:
                for j in range(i + 2, directory_len, 2):
                    next_offset = directory[j]
                    if next_offset > 0:
                        with BytesIO(data[header_offset:next_offset]) as buf:
                            animations.append(Animation.read(buf, header_size=header_size))
                        break
                else:
                    with BytesIO(data[header_offset:]) as buf:
                        animations.append(Animation.read(buf, header_size=header_size))
        # we read the whole first sector as the directory, but there aren't that many entries, so delete all the dummy
        # empty entries we added at the end
        while animations and not animations[-1]:
            del animations[-1]
        return cls(animations)

    def write(self, f: BinaryIO, **kwargs):
        directory = []
        directory_offset = f.tell()
        f.write(bytes(self.SECTOR_SIZE + 4))
        offset = 0
        for animation in self.animations:
            if animation is None:
                directory.append((0, 0))
            else:
                directory.append((offset, offset + animation.header_len))
                start = f.tell()
                animation.write(f)
                offset += f.tell() - start

        end = f.tell()
        f.seek(directory_offset)
        for header_offset, data_offset in directory:
            f.write(header_offset.to_bytes(4, 'little'))
            f.write(data_offset.to_bytes(4, 'little'))
        f.seek(directory_offset + self.SECTOR_SIZE)
        f.write(offset.to_bytes(4, 'little'))
        f.seek(end)


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
