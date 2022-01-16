from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum
from typing import BinaryIO, ByteString, Iterable

from PIL import Image


@dataclass
class Block:
    x: int
    y: int
    width: int
    height: int
    data: bytes


class BitsPerPixel(IntEnum):
    BPP_4 = 0
    BPP_8 = 1
    BPP_16 = 2
    BPP_24 = 3


class Tim:
    """An image in the PSX TIM format"""

    MAGIC = b'\x10'
    VERSION = b'\0'

    def __init__(self):
        """Create a new, empty TIM image"""
        self.raw_clut_bounds = (0, 0, 0, 0)
        self.raw_image_bounds = (0, 0, 0, 0)
        self.palettes = []
        self.image_data = b''
        self.width = self.height = 0
        self.bpp = None

    @staticmethod
    def _decode_pixel_16(pixel_data: bytes) -> list[tuple[int, int, int, int]]:
        pixels = []
        for i in range(0, len(pixel_data), 2):
            pixel = int.from_bytes(pixel_data[i:i + 2], 'little')
            r = pixel & 0x1f
            g = (pixel >> 5) & 0x1f
            b = (pixel >> 10) & 0x1f
            stp = (pixel >> 15) != 0
            if r == g == b == 0:
                stp = not stp  # transparency flag has opposite meaning for black pixels
            pixels.append((r << 3, g << 3, b << 3, 0 if stp else 0xff))
        return pixels

    @staticmethod
    def _encode_pixel_16(pixel_data: list[tuple[int, int, int, int]]) -> bytes:
        out = bytearray()
        for r, g, b, a in pixel_data:
            pixel = r >> 3
            pixel |= (g >> 3) << 5
            pixel |= (b >> 3) << 10
            stp = a == 0
            if r == g == b == 0:
                stp = not stp  # transparency flag has opposite meaning for black pixels
            if stp:
                pixel |= 0x8000
            out += pixel.to_bytes(2, 'little')
        return bytes(out)

    @staticmethod
    def _decode_pixel_24(pixel_data: bytes) -> list[tuple[int, int, int, int]]:
        pixels = []
        for i in range(0, len(pixel_data), 3):
            r = pixel_data[i]
            g = pixel_data[i+1]
            b = pixel_data[i+2]
            pixels.append((r, g, b, 0xff))
        return pixels

    def set_clut(self, data: ByteString, width: int, x: int = 0, y: int = 0):
        """
        Set the CLUT (color lookup table) for this TIM image

        The CLUT contains one or more color palettes that can be selected for 4-bit and 8-bit images.

        :param data: The raw CLUT data
        :param width: Width of a CLUT palette in 16-bit integers
        :param x: x offset of the CLUT in the frame buffer
        :param y: y offset of the CLUT in the frame buffer
        """
        row_size = width*2
        for i in range(0, len(data), row_size):
            palette = data[i:i+row_size]
            if len(palette) != row_size:
                raise ValueError('CLUT size is incorrect')
            self.palettes.append(self._decode_pixel_16(palette))
        self.raw_clut_bounds = (x, y, width, len(self.palettes))

    def set_image(self, data: ByteString, bpp: BitsPerPixel, width: int, x: int = 0, y: int = 0):
        """
        Set the image data of the TIM

        :param data: The raw image data
        :param bpp: Bits-per-pixel of the image data
        :param width: Width of an image row in 16-bit integers (NOT in pixels)
        :param x: x offset of the image in the frame buffer
        :param y: y offset of the image in the frame buffer
        """
        self.bpp = bpp
        self.image_data = data
        self.height = len(data) // (width*2)
        match self.bpp:
            case BitsPerPixel.BPP_4:
                self.width = width*4
            case BitsPerPixel.BPP_8:
                self.width = width*2
            case BitsPerPixel.BPP_16:
                self.width = width
            case BitsPerPixel.BPP_24:
                self.width = width*2//3
        self.raw_image_bounds = (x, y, width, self.height)

    @property
    def num_palettes(self) -> int:
        """Number of palettes in the CLUT, if any"""
        return len(self.palettes)

    def _get_clut_indexes(self) -> Iterable[int]:
        if self.bpp == BitsPerPixel.BPP_4:
            for b in self.image_data:
                yield b & 0x0f
                yield b >> 4
        else:  # BPP_8
            yield from self.image_data

    def _get_clut_pixels(self, clut_index: int) -> list[tuple[int, int, int, int]]:
        return [self.palettes[clut_index][pixel_index] for pixel_index in self._get_clut_indexes()]

    def get_pixels(self, clut_index: int = 0) -> list[tuple[int, int, int, int]]:
        """
        Convert the TIM image data to pixels

        :param clut_index: If the image uses a CLUT, the index of the palette in the CLUT to use
        :return: A list of (R, G, B, A) tuples
        """
        match self.bpp:
            case BitsPerPixel.BPP_4 | BitsPerPixel.BPP_8:
                return self._get_clut_pixels(clut_index)
            case BitsPerPixel.BPP_16:
                return self._decode_pixel_16(self.image_data)
            case BitsPerPixel.BPP_24:
                return self._decode_pixel_24(self.image_data)

    def to_image(self, clut_index: int = 0, with_transparency: bool = True) -> Image:
        """
        Convert the TIM image to a Pillow image

        :param clut_index: If the image uses a CLUT, the index of the palette in the CLUT to use
        :param with_transparency: If True, return an RGBA image; otherwise, an RGB image
        :return: The converted image
        """
        pixels = self.get_pixels(clut_index)
        if with_transparency:
            return Image.frombytes('RGBA', (self.width, self.height), b''.join(bytes(pixel) for pixel in pixels))
        else:
            return Image.frombytes('RGB', (self.width, self.height), b''.join(bytes(pixel[:3]) for pixel in pixels))

    @staticmethod
    def _read_block(source: BinaryIO) -> Block:
        size = int.from_bytes(source.read(4), 'little')
        data = source.read(size - 4)
        x = int.from_bytes(data[:2], 'little')
        y = int.from_bytes(data[2:4], 'little')
        width = int.from_bytes(data[4:6], 'little')
        height = int.from_bytes(data[6:8], 'little')
        return Block(x, y, width, height, data[8:])

    @staticmethod
    def _write_block(block: Block, destination: BinaryIO):
        destination.write((block.width * block.height * 2 + 12).to_bytes(4, 'little'))
        destination.write(block.x.to_bytes(2, 'little'))
        destination.write(block.y.to_bytes(2, 'little'))
        destination.write(block.width.to_bytes(2, 'little'))
        destination.write(block.height.to_bytes(2, 'little'))
        destination.write(block.data)

    @classmethod
    def read(cls, source: BinaryIO) -> Tim:
        """
        Read a TIM image from a provided data source

        :param source: Binary data source to read the image from
        :return: The TIM image
        """
        if source.read(1) != cls.MAGIC:
            raise ValueError('Not a valid TIM image')

        version = source.read(1)
        if version != cls.VERSION:
            raise NotImplementedError(f'Unknown/unsupported TIM version {version}')

        source.seek(2, 1)  # 2 unused bytes
        flags = int.from_bytes(source.read(4), 'little')
        has_clut = (flags & 8) != 0
        bpp = BitsPerPixel(flags & 3)

        tim = cls()
        if has_clut:
            clut = cls._read_block(source)
            tim.set_clut(clut.data, clut.width, clut.x, clut.y)

        image = cls._read_block(source)
        tim.set_image(image.data, bpp, image.width, image.x, image.y)

        return tim

    def write(self, destination: BinaryIO):
        """
        Write the raw TIM image to a file-like object

        :param destination: File-like object to write the TIM image to
        """
        destination.write(self.MAGIC)
        destination.write(self.VERSION)
        destination.write(b'\0\0')  # 2 unused bytes
        has_clut = len(self.palettes) > 0
        flags = self.bpp | (8 if has_clut else 0)
        destination.write(flags.to_bytes(4, 'little'))

        if has_clut:
            clut = b''.join(self._encode_pixel_16(palette) for palette in self.palettes)
            x, y, w, h = self.raw_clut_bounds
            self._write_block(Block(x, y, w, h, clut), destination)

        x, y, w, h = self.raw_image_bounds
        self._write_block(Block(x, y, w, h, self.image_data), destination)