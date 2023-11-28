import base64
import io
import struct
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import BinaryIO, Self, Iterable

from galsdk.format import Archive
from galsdk.tim import TimFormat
from galsdk.util import file as util
from psx.tim import Tim


@dataclass
class CreditControl:
    unknown: int
    rects: list[tuple[int, int, int, int]]
    data: list[list[bytes]]


class BitReader:
    def __init__(self, f: BinaryIO):
        self.f = f
        self.read_bit = 0x80
        self.byte = 0

    def read_bits(self, num_bits: int) -> int:
        out = 0
        current_bit = 1 << (num_bits - 1)

        while current_bit != 0:
            if self.read_bit == 0x80:
                self.byte = self.f.read(1)[0]

            if self.byte & self.read_bit:
                out |= current_bit

            current_bit >>= 1
            self.read_bit >>= 1
            if self.read_bit == 0:
                self.read_bit = 0x80

        return out


class Credits(Archive[Tim]):
    def __init__(self, control: list[CreditControl], images: list[TimFormat] = None):
        super().__init__()
        self.control = control
        self.images = images or []

    @property
    def supports_nesting(self) -> bool:
        return False

    @property
    def metadata(self) -> dict[str, list[dict[str, int | list[list[bytes]] | list[tuple[int, int, int, int]]]]]:
        metadata = {'control': []}
        for control in self.control:
            cd = asdict(control)
            for row in cd['data']:
                for i in range(len(row)):
                    row[i] = base64.b64encode(row[i]).decode()
            metadata['control'].append(cd)
        return metadata

    # PyCharm thinks that all the values of this dictionary are strings, even though it says right there that they can
    # be other stuff
    # noinspection PyTypeChecker
    # noinspection PyUnresolvedReferences
    @classmethod
    def from_metadata(cls, metadata: dict[str, bool | int | float | str | list | tuple | dict]) -> Self:
        control = []
        for cd in metadata['control']:
            for row in cd['data']:
                for i in range(len(row)):
                    row[i] = base64.b64decode(row[i])
            control.append(CreditControl(cd['unknown'], cd['rects'], cd['data']))
        return cls(control)

    def __getitem__(self, item: int) -> Tim:
        return self.images[item]

    def __setitem__(self, key: int, value: Tim):
        self.images[key] = TimFormat.from_tim(value)

    def __delitem__(self, key: int):
        del self.images[key]

    def __iter__(self) -> Iterable[Tim]:
        yield from self.images

    def __len__(self) -> int:
        return len(self.images)

    def append(self, item: Tim):
        raise NotImplementedError

    def append_raw(self, item: bytes):
        raise NotImplementedError

    @classmethod
    def import_explicit(cls, paths: Iterable[Path], fmt: str = None) -> Self:
        raise NotImplementedError

    def unpack_one(self, path: Path, index: int) -> Path:
        item = self.images[index]
        new_path = path.with_suffix('.TIM')
        with new_path.open('wb') as f:
            item.write(f)
        return new_path

    @property
    def suggested_extension(self) -> str:
        return '.CRD'

    @classmethod
    def read(cls, f: BinaryIO, **kwargs) -> Self:
        f.seek(4)  # "size" elements in the header are unused
        header_size = int.from_bytes(f.read(4), 'little')
        f.seek(0)
        raw_header = f.read(header_size)
        num_ints = header_size >> 2
        header = struct.unpack_from(f'<{num_ints}I', raw_header, 0)
        control = []
        images = []
        for i in range(len(header) >> 1):
            # the "size" element of the header is unused
            offset = header[i * 2 + 1]
            f.seek(offset)

            if i < 3:
                # control entries
                end = header[(i + 1) * 2 + 1]
                unknown, num_rects = struct.unpack('<2H', f.read(4))
                rects = []
                control_data = []
                for j in range(num_rects):
                    rects.append(struct.unpack('<4H', f.read(8)))

                while f.tell() < end:
                    num_data = int.from_bytes(f.read(4), 'little')
                    if num_data == 0:
                        break
                    data_row = []
                    for j in range(num_data):
                        data_row.append(util.read_some(f, 0x20))
                    control_data.append(data_row)

                control.append(CreditControl(unknown, rects, control_data))
            else:
                # images
                reader = BitReader(f)
                buf = bytearray()
                buf_window = bytearray(0x1000)
                window_index = 1
                while True:
                    while reader.read_bits(1) != 0:
                        byte = reader.read_bits(8)
                        buf.append(byte)
                        buf_window[window_index] = byte
                        window_index = (window_index + 1) & 0xfff

                    window_offset = reader.read_bits(12)
                    if window_offset == 0:
                        break

                    byte_count = reader.read_bits(4) + 1
                    # the extra +1 matches the game logic
                    for j in range(byte_count + 1):
                        index = (window_offset + j) & 0xfff
                        byte = buf_window[index]
                        buf.append(byte)
                        buf_window[window_index] = byte
                        window_index = (window_index + 1) & 0xfff

                buf_io = io.BytesIO(buf)
                images.append(TimFormat.read(buf_io))

        return cls(control, images)

    def write(self, f: BinaryIO, **kwargs):
        raise NotImplementedError

    def export(self, path: Path, fmt: str = None) -> Path:
        if fmt is None:
            fmt = 'png'
        path.mkdir(exist_ok=True)
        for i, image in enumerate(self.images):
            image_path = path / f'{i:03}'
            image.export(image_path, fmt)
        return path
