import os
import shutil
from pathlib import Path
from typing import BinaryIO, Literal, TextIO, overload

from panda3d.core import Geom, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter, StringStream, \
    PNMImage, Texture
from PIL.Image import Image
import io
import numpy as np


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


def make_triangle(p1: tuple[float, float], p2: tuple[float, float], p3: tuple[float, float]) -> Geom:
    vdata = GeomVertexData('', GeomVertexFormat.getV3(), Geom.UHStatic)
    vdata.setNumRows(3)

    vertex = GeomVertexWriter(vdata, 'vertex')
    vertex.addData3(p1[0], p1[1], 0)
    vertex.addData3(p2[0], p2[1], 0)
    vertex.addData3(p3[0], p3[1], 0)

    primitive = GeomTriangles(Geom.UHStatic)
    primitive.addVertices(0, 1, 2)
    primitive.closePrimitive()

    geom = Geom(vdata)
    geom.addPrimitive(primitive)
    return geom


def make_quad(p1: tuple[float, float], p2: tuple[float, float], p3: tuple[float, float],
              p4: tuple[float, float], use_texture: bool = False) -> Geom:
    vertex_format = GeomVertexFormat.getV3t2() if use_texture else GeomVertexFormat.getV3()
    vdata = GeomVertexData('', vertex_format, Geom.UHStatic)
    vdata.setNumRows(4)

    vertex = GeomVertexWriter(vdata, 'vertex')
    vertex.addData3(p1[0], p1[1], 0)
    vertex.addData3(p2[0], p2[1], 0)
    vertex.addData3(p3[0], p3[1], 0)
    vertex.addData3(p4[0], p4[1], 0)

    if use_texture:
        texcoord = GeomVertexWriter(vdata, 'texcoord')
        texcoord.addData2(0, 0)
        texcoord.addData2(1, 0)
        texcoord.addData2(1, 1)
        texcoord.addData2(0, 1)

    primitive = GeomTriangles(Geom.UHStatic)
    primitive.addVertices(0, 1, 2)
    primitive.addVertices(2, 3, 0)
    primitive.closePrimitive()

    geom = Geom(vdata)
    geom.addPrimitive(primitive)
    return geom


def create_texture_from_image(image: Image) -> Texture:
    buffer = io.BytesIO()
    image.save(buffer, format='png')

    panda_image = PNMImage()
    panda_image.read(StringStream(buffer.getvalue()))

    texture = Texture()
    texture.load(panda_image)
    return texture


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
        try:
            new_height = original_height * (new_width / original_width)
        except ZeroDivisionError:
            new_height = 0
    else:
        new_height = min(available_height, original_height * max_scale)
        try:
            new_width = original_width * (new_height / original_height)
        except ZeroDivisionError:
            new_width = 0

    if new_width > available_width:
        new_height *= available_width / new_width
        new_width = available_width

    if new_height > available_height:
        new_width *= available_height / new_height
        new_height = available_height

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
