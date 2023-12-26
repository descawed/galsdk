from __future__ import annotations

import json
import struct
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from PIL import Image

from galsdk.tile import TileSet
from psx.tim import Tim


@dataclass
class Color:
    index: int


@dataclass
class Pause:
    event: int


YesNo = object()
Wait = object()


class Font(ABC):
    CHAR_WIDTH = 0
    CHAR_HEIGHT = 0

    @abstractmethod
    def draw(self, text: bytes, stage_index: int, bg_color: tuple[int, int, int, int] = (0, 0, 0, 0)) -> Image.Image:
        pass

    @classmethod
    @abstractmethod
    def load(cls, path: Path) -> Self:
        pass


class LatinFont(Font):
    """The in-game font for Western versions of the game"""

    CHAR_WIDTH = 16
    CHAR_HEIGHT = 16
    SPACE_WIDTH = 8
    LINE_HEIGHT = 15
    TAB_WIDTH = 1
    WRAP_WIDTH = 320 - CHAR_WIDTH  # 320 is the horizontal screen resolution

    def __init__(self, image: Tim, char_widths: dict[int, int]):
        self.tile_set = TileSet(image, self.CHAR_WIDTH, self.CHAR_HEIGHT)
        # the game always subtracts one when adding the char width
        self.char_widths = {c: w - 1 for c, w in char_widths.items()}

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
                        elif c in b'\t':
                            current_width += self.SPACE_WIDTH * self.TAB_WIDTH
                        else:
                            current_width += self.char_widths[c]
                            if self.WRAP_WIDTH < current_width:
                                # wrap the line
                                new_width = 0
                                for i in range(len(result) - 1, -1, -1):
                                    wrap_c = result[i]
                                    if wrap_c in b' \t\r\n':
                                        result.insert(i + 1, b'\n')
                                        height += self.LINE_HEIGHT
                                        current_width -= new_width
                                        if current_width > max_width:
                                            max_width = current_width
                                        current_width = new_width
                                        break
                                    elif wrap_c in self.char_widths:
                                        new_width += self.char_widths[c]
                        result.append(c)
                case 'function':
                    if c in b'p':
                        expect = 'pause'
                    elif c in b'c':
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
                            height += self.LINE_HEIGHT
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
        # since we subtract 1 when adding the width for each character, the last column of pixels is cut off unless we
        # add 1 here
        return result, max_width + 1, height

    def draw(self, text: bytes, stage_index: int = 0,
             bg_color: tuple[int, int, int, int] = (0, 0, 0, 0)) -> Image.Image:
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
                y += self.LINE_HEIGHT
            elif elem in b' ':
                x += self.SPACE_WIDTH
            elif elem in b'\t':
                x += self.SPACE_WIDTH * self.TAB_WIDTH
            else:
                # regular character
                width = self.char_widths[elem]
                char = self.tile_set.get(elem - 0x20, clut)
                image.alpha_composite(char, (x, y))
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


class JapaneseFont(Font):
    """The in-game font for the Japanese version of the game"""

    CHAR_WIDTH = 14
    CHAR_HEIGHT = 14

    def __init__(self, basic: Tim, kanji: list[Tim]):
        self.basic = TileSet(basic, self.CHAR_WIDTH, self.CHAR_HEIGHT)
        self.kanji = [TileSet(image, self.CHAR_WIDTH, self.CHAR_HEIGHT) for image in kanji]

    def _calculate_size(self, string: list[int]) -> tuple[int, int]:
        max_width = current_width = 0
        height = 0
        new_line = True
        for c in string:
            if c & 0xc000:
                if (c & 0xff) in [1, 4]:
                    if current_width > max_width:
                        max_width = current_width
                    current_width = 0
                    new_line = True
            else:
                current_width += self.CHAR_WIDTH
                if new_line:
                    height += self.CHAR_HEIGHT
                    new_line = False

        if current_width > max_width:
            max_width = current_width
        return max_width, height

    def draw(self, text: bytes | list[int], stage_index: int,
             bg_color: tuple[int, int, int, int] = (0, 0, 0, 0)) -> Image.Image:
        if isinstance(text, bytes):
            text = list(struct.unpack(f'<{len(text) >> 1}H', text))
        width, height = self._calculate_size(text)
        image = Image.new('RGBA', (width, height), bg_color)
        x = y = clut = 0
        i = 0
        while i < len(text):
            code = text[i]
            if code & 0xc000:
                control_code = code & 0xff
                match control_code:
                    case 1 | 4:
                        x = 0
                        y += self.CHAR_HEIGHT
                    case 3:
                        i += 1
                    case 6:
                        i += 1
                        clut = text[i]
            else:
                # regular character
                if code & 0x800:
                    char = self.kanji[stage_index].get(code & 0xff, clut)
                else:
                    char = self.basic.get(code, clut)

                image.paste(char, (x, y))
                x += self.CHAR_WIDTH
            i += 1
        return image

    @classmethod
    def load(cls, path: Path) -> JapaneseFont:
        json_path = path / 'font.json'
        with json_path.open() as f:
            info = json.load(f)
        basic_path = path / info['image']
        with basic_path.open('rb') as f:
            basic = Tim.read(f)
        kanji = []
        for kanji_set in info['kanji']:
            kanji_path = path / kanji_set['image']
            with kanji_path.open('rb') as f:
                kanji.append(Tim.read(f))
        return cls(basic, kanji)
