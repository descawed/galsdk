from __future__ import annotations

import argparse
from enum import IntEnum
from pathlib import Path
from typing import BinaryIO

from PIL import Image


class PixelStorageFormat(IntEnum):
    PSMCT32 = 0
    PSMCT24 = 1
    PSMCT16 = 2
    PSMCT16S = 10
    PSMT8 = 19
    PSMT4 = 20
    PSMT8H = 27
    PSMT4HL = 36
    PSMT4HH = 44
    PSMZ32 = 48
    PSMZ24 = 49
    PSMZ16 = 50
    PSMZ16S = 58


class Texture:
    MAGIC = b'TEX\xA0'

    def __init__(self, psf: PixelStorageFormat, width: int = 0, height: int = 0, palettes: list[list[bytes]] = None,
                 image_data: bytes = None):
        self.psf = psf
        self.width = width
        self.height = height
        self.palettes = palettes or []
        self.image_data = image_data or b''

    @classmethod
    def read(cls, f: BinaryIO) -> Texture:
        magic = f.read(4)
        if magic != cls.MAGIC:
            raise ValueError('Not a TEX image')

        f.seek(12, 1)
        psf = PixelStorageFormat(int.from_bytes(f.read(4), 'little'))
        f.seek(4, 1)
        clut_block_offset = int.from_bytes(f.read(4), 'little')
        f.seek(12, 1)
        image_block_offset = int.from_bytes(f.read(4), 'little')

        f.seek(clut_block_offset + 0x60)
        match psf:
            case PixelStorageFormat.PSMT4:
                palette = [f.read(4) for _ in range(16)]
            case PixelStorageFormat.PSMT8:
                palette = [f.read(4) for _ in range(256)]
                # swizzle(?) palette
                for i in range(8, 256, 32):
                    row = palette[i:i + 8]
                    neighbor = palette[i + 8:i + 16]
                    palette[i + 8:i + 16] = row
                    palette[i:i + 8] = neighbor
            case _:
                raise NotImplementedError(f'Only PSMT4 and PSMT8 formats are supported; found {psf.name}')

        f.seek(image_block_offset + 0x30)
        width = int.from_bytes(f.read(4), 'little')
        height = int.from_bytes(f.read(4), 'little')

        f.seek(0x28, 1)
        image_data = f.read()

        # I figured out the correct swizzling of the palette by dumping a texture from PCSX2 and then using this
        # to map it back to the correct palette indexes
        # sample = Image.open('~/Pictures/gash_palette_sample.png')
        # raw_sample = sample.crop((0, 0, width, height)).convert('RGBA').tobytes()
        # correct_palette = [b'\0\0\0\0'] * 256
        # for x in range(width):
        #     for y in range(height):
        #         offset = y * width * 4 + x * 4
        #         sample_pixel = raw_sample[offset:offset + 3] + b'\x80'
        #         index = image_data[y * width + x]
        #         correct_palette[index] = sample_pixel
        # with open('~/galerians/ash/test_palette.bin', 'wb') as f:
        #     f.write(b'\0' * 0xA0)
        #     f.write(b''.join(correct_palette))

        return cls(psf, width, height, [palette], image_data)

    def to_image(self, palette_index: int = 0) -> Image.Image:
        pixels = bytearray()
        palette = self.palettes[palette_index]
        match self.psf:
            case PixelStorageFormat.PSMT8:
                for i in self.image_data:
                    pixels += palette[i]
            case PixelStorageFormat.PSMT4:
                for i in self.image_data:
                    pixels += palette[i & 0xf]
                    pixels += palette[i >> 4]
            case _:
                raise NotImplementedError

        for i in range(3, len(pixels), 4):
            alpha = pixels[i]
            if alpha > 0x80:
                alpha = 0x80
            pixels[i] = int(alpha * 255 / 128)

        return Image.frombytes('RGBA', (self.width, self.height), bytes(pixels))


def convert(texture_path: Path, output_path: Path):
    with texture_path.open('rb') as f:
        texture = Texture.read(f)
    texture.to_image().save(output_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Convert Galerians: Ash texture files')
    parser.add_argument('texture', type=Path, help='Texture file to convert')
    parser.add_argument('output', type=Path, help='Converted image file to create')

    args = parser.parse_args()
    convert(args.texture, args.output)
