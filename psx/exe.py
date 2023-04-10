from __future__ import annotations

from enum import Enum
from typing import BinaryIO


class Region(str, Enum):
    NTSC_U = 'NTSC-U'
    NTSC_J = 'NTSC-J'
    PAL = 'PAL'

    def __str__(self):
        return self.value


# TODO: use bytearray and memoryview
class Exe:
    """A PSX executable"""

    MAGIC = b'PS-X EXE'
    REGION_MARKERS = {
        Region.NTSC_U: b'Sony Computer Entertainment Inc. for North America area',
        Region.NTSC_J: b'Sony Computer Entertainment Inc. for Japan area',
        Region.PAL: b'Sony Computer Entertainment Inc. for Europe area',
    }
    MARKER_REGIONS = {marker: region for region, marker in REGION_MARKERS.items()}
    HEADER_SIZE = 0x800

    def __init__(self, load_address: int, region: Region = Region.NTSC_U):
        self.region = region
        self.marker = self.REGION_MARKERS[self.region]
        self.entry_point = 0x80010000
        self.global_pointer = 0
        self.stack_pointer = 0x801ffff0
        self.load_address = load_address
        self.data = b''

    def _get_address_slice(self, item: slice | int) -> tuple[int, int, int]:
        if isinstance(item, slice):
            start = item.start
            stop = item.stop
            step = item.step
        elif isinstance(item, int):
            start = item
            stop = start + 1
            step = 1
        else:
            raise TypeError(f'Invalid address {item}')

        start -= self.load_address
        stop -= self.load_address
        if start < 0 or stop < start:
            raise ValueError('Invalid address')
        return start, stop, step

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, item: slice | int) -> bytes:
        start, stop, step = self._get_address_slice(item)
        return self.data[start:stop:step]

    def __setitem__(self, key: slice | int, value: bytes):
        start, stop, step = self._get_address_slice(key)
        if len(value) != stop - start:
            raise ValueError('Value is not the same size as the address region')
        if step != 1:
            raise ValueError('Step not supported when setting')
        self.data = self.data[:start] + value + self.data[stop:]

    @classmethod
    def read(cls, source: BinaryIO) -> Exe:
        magic = source.read(8)
        if magic != cls.MAGIC:
            raise ValueError('Not a valid PSX EXE')
        source.seek(8, 1)
        entry_point = int.from_bytes(source.read(4), 'little')
        global_pointer = int.from_bytes(source.read(4), 'little')
        load_address = int.from_bytes(source.read(4), 'little')
        source.seek(0x14, 1)
        stack_pointer = int.from_bytes(source.read(4), 'little')
        source.seek(0x18, 1)
        marker = b''
        while (c := source.read(1)) != b'\0':
            marker += c
        region = cls.MARKER_REGIONS.get(marker)
        source.seek(cls.HEADER_SIZE)
        data = source.read()

        exe = cls(load_address)
        exe.region = region
        exe.marker = marker
        exe.entry_point = entry_point
        exe.global_pointer = global_pointer
        exe.stack_pointer = stack_pointer
        exe.data = data

        return exe

    def write(self, destination: BinaryIO):
        data_len = len(self.data)
        data_pad = data_len % 2048  # data size must be a multiple of 2048
        data_len += data_pad

        destination.write(self.MAGIC)
        destination.write(b'\0' * 8)
        destination.write(self.entry_point.to_bytes(4, 'little'))
        destination.write(self.global_pointer.to_bytes(4, 'little'))
        destination.write(self.load_address.to_bytes(4, 'little'))
        destination.write(data_len.to_bytes(4, 'little'))
        destination.write(b'\0' * 0x10)
        destination.write(self.stack_pointer.to_bytes(4, 'little'))
        destination.write(b'\0' * 0x18)
        destination.write(self.marker)
        header_left = self.HEADER_SIZE - destination.tell()
        destination.write(b'\0' * header_left)
        destination.write(self.data)
        if data_pad > 0:
            destination.write(b'\0' * data_pad)
