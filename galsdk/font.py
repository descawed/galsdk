from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from psx.tim import Tim


@dataclass
class Color:
    index: int


@dataclass
class Pause:
    event: int


YesNo = object()
Wait = object()


class Font:
    """The in-game font"""

    CHAR_WIDTH = 16
    CHAR_HEIGHT = 16
    SPACE_WIDTH = 8

    def __init__(self, image: Tim, char_widths: dict[int, int]):
        self.image = image
        self.char_widths = char_widths
        self.cluts = [self.image.to_image(i) for i in range(16)]

    def _parse_string(self, string: bytes) -> tuple[list, int, int]:
        expect = 'char'
        result = []
        max_width = current_width = 0
        height = self.CHAR_HEIGHT
        operand = bytearray()
        for c in string:
            match expect:
                case 'char':
                    if c in b'$':
                        expect = 'function'
                    else:
                        if c in b' ':
                            current_width += self.SPACE_WIDTH
                        else:
                            current_width += self.char_widths[c]
                        result.append(c)
                case 'function':
                    if c in b'pc':
                        if c in b'p':
                            expect = 'pause'
                        else:
                            expect = 'color'
                    else:
                        if c in b'$':
                            # literal dollar sign
                            current_width += self.char_widths[c]
                            result.append(c)
                        elif c in b'l':
                            result.append(b'\r')
                            current_width = 0
                        elif c in b'r':
                            result.append(b'\n')
                            if current_width > max_width:
                                max_width = current_width
                            current_width = 0
                            height += self.CHAR_HEIGHT
                        elif c in b'w':
                            result.append(Wait)
                        elif c in b'y':
                            result.append(YesNo)
                        else:
                            raise ValueError(f'Unknown function {chr(c)}')
                        expect = 'char'
                case 'pause' | 'color':
                    if c not in b'(':
                        raise ValueError('Invalid function syntax')
                    expect = 'pause_operand' if expect == 'pause' else 'color_operand'
                    operand = bytearray()
                case 'pause_operand' | 'color_operand':
                    if c in b')':
                        value = int(operand)
                        obj = Pause(value) if expect == 'pause_operand' else Color(value)
                        result.append(obj)
                        expect = 'char'
                    else:
                        operand.append(c)
        if current_width > max_width:
            max_width = current_width
        return result, max_width, height

    def draw(self, text: bytes, bg_color: tuple[int, int, int, int] = (0, 0, 0, 0)) -> Image:
        parsed, width, height = self._parse_string(text)
        image = Image.new('RGBA', (width, height), bg_color)
        x = y = clut = 0
        for elem in parsed:
            if isinstance(elem, Color):
                clut = elem.index
            elif isinstance(elem, Pause) or elem is Wait or elem is YesNo:
                pass
            elif elem == b'\r':
                x = 0
            elif elem == b'\n':
                x = 0
                y += self.CHAR_HEIGHT
            elif elem in b' ':
                x += self.SPACE_WIDTH
            else:
                # regular character
                char_index = elem - 0x20
                font_x = char_index % 16 * self.CHAR_WIDTH
                font_y = char_index // 16 * self.CHAR_HEIGHT
                width = self.char_widths[elem]
                char = self.cluts[clut].crop((font_x, font_y, font_x + self.CHAR_WIDTH, font_y + self.CHAR_HEIGHT))
                image.paste(char, (x, y))
                x += width
        return image

    @classmethod
    def load(cls, path: Path) -> Font:
        json_path = path / 'font.json'
        with json_path.open() as f:
            info = json.load(f)
        image_path = path / info['image']
        with image_path.open('rb') as f:
            image = Tim.read(f)
        char_widths = {int(k): v for k, v in info['widths'].items()}
        return cls(image, char_widths)

    def save(self, path: Path, image_name: str):
        image_path = path / image_name
        with image_path.open('wb') as f:
            self.image.write(f)

        json_path = path / 'font.json'
        with json_path.open('w') as f:
            json.dump({'image': image_name, 'widths': self.char_widths}, f)
