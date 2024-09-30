from __future__ import annotations

import struct
from abc import abstractmethod
from pathlib import Path
from typing import BinaryIO, Iterator, Self

from galsdk.format import FileFormat


class StringDb(FileFormat):
    @classmethod
    @abstractmethod
    def encode(cls, string: str, stage_index: int) -> bytes:
        """Encode a string for storage in the database for the given stage_index"""

    @classmethod
    @abstractmethod
    def decode(cls, data: bytes, stage_index: int) -> str:
        """Decode a string from the database using the given stage_index"""

    @abstractmethod
    def __getitem__(self, item: int) -> str:
        """Get a string from the database"""

    @abstractmethod
    def __delitem__(self, item: int):
        """Delete a string from the database"""

    @abstractmethod
    def __setitem__(self, key: int, value: str | bytes):
        """Change a string in the database"""

    @abstractmethod
    def __iter__(self) -> Iterator[str]:
        """Iterate over the strings in the database"""

    @abstractmethod
    def __len__(self) -> int:
        """Number of strings in the database"""

    @abstractmethod
    def iter_raw(self) -> Iterator[bytes]:
        """Iterate over the strings as raw (un-decoded) bytes"""

    @abstractmethod
    def iter_both(self) -> Iterator[tuple[bytes, str]]:
        """Iterate over the strings as both raw and decoded strings"""

    @abstractmethod
    def append(self, string: str) -> int:
        """
        Append a string to the database

        :param string: The string to append to the database
        :return: The ID of the newly-appended string
        """

    @abstractmethod
    def insert(self, index: int, string: str) -> int:
        """
        Insert a string into the database at the given index

        :param index: The index at which to insert the string
        :param string: The string to insert
        :return: The ID of the newly-inserted string
        """

    @abstractmethod
    def append_raw(self, string: bytes) -> int:
        """
        Append a raw byte string to the database with no encoding applied

        :param string: The byte string to append to the database
        :return: The ID of the newly-appended string
        """

    @abstractmethod
    def clear(self):
        """Delete all strings in the database"""

    @abstractmethod
    def import_in_place(self, path: Path):
        """Replace the contents of this database with those imported from the given path"""

    @abstractmethod
    def get_by_id(self, string_id: int) -> str:
        """Get a string from the database with the ID used by the game engine"""

    @abstractmethod
    def get_index_from_id(self, string_id: int) -> int:
        """Get a string's index in the database with the ID used by the game engine"""

    @abstractmethod
    def get_id_from_index(self, index: int) -> int:
        """Get a string's ID used by the game engine with its index in the database"""

    @abstractmethod
    def iter_ids(self) -> Iterator[tuple[int, str]]:
        """Iterate through the strings in the database as (ID, string) pairs"""

    @abstractmethod
    def iter_both_ids(self) -> Iterator[tuple[int, tuple[bytes, str]]]:
        """Iterate over the strings as both raw and decoded strings with their IDs"""


# we keep everything as bytes internally because there are some cases where there are bogus characters in the data
# that we don't want to overwrite unless requested
class LatinStringDb(StringDb):
    """
    A database of text strings used within a game stage

    The game keeps the message strings for each stage in one database file per stage. These databases are similar to
    but not the same as the CDB database files; each entry is a single null-terminated string rather than a file.
    Strings are referenced in code by their index in these databases.
    """
    MAGIC = b'\x41\x84'
    DEFAULT_ENCODING = 'windows-1252'

    strings: list[bytes]

    def __init__(self, encoding: str = DEFAULT_ENCODING):
        """
        Create a new string database with a given encoding

        :param encoding: Character encoding to use for strings in the database
        """
        self.strings = []
        self.encoding = encoding

    @property
    def suggested_extension(self) -> str:
        return '.SDB'

    @staticmethod
    def _import_static(db: LatinStringDb, path: Path):
        with open(path, 'rb') as f:
            s = b''
            while c := f.read(1):
                if c == b'\n':
                    db.append_raw(s.rstrip(b'\r'))
                    s = b''
                else:
                    s += c
            if s:
                db.append_raw(s)

    def import_in_place(self, path: Path):
        self.clear()
        self._import_static(self, path)

    @classmethod
    def import_(cls, path: Path, fmt: str = None) -> Self:
        db = cls()
        cls._import_static(db, path)
        return db

    def export(self, path: Path, fmt: str = None) -> Path:
        new_path = path.with_suffix('.txt')
        with new_path.open('wb') as f:
            for string in self.strings:
                f.write(string + b'\n')
        return new_path

    @classmethod
    def read(cls, f: BinaryIO, **kwargs) -> Self:
        """
        Read a string database file

        :param f: Binary data stream to read the string database from
        """
        db = cls()
        magic = f.read(2)
        if magic != cls.MAGIC:
            raise ValueError('Not a string database')
        num_strings = int.from_bytes(f.read(2), 'little')
        offsets = [int.from_bytes(f.read(4), 'little') for _ in range(num_strings)]
        for offset in offsets:
            f.seek(offset)
            data = b''
            while c := f.read(1):
                if c == b'\0':
                    break
                data += c
            db.append_raw(data)
        return db

    def write(self, f: BinaryIO, **kwargs):
        """
        Write the strings in this object out to a database file

        :param f: Binary data stream to write the string database to
        """
        header_size = (len(self.strings) + 1)*4
        f.write(self.MAGIC)
        f.write(len(self.strings).to_bytes(2, 'little'))
        pos = header_size
        for s in self.strings:
            f.write(pos.to_bytes(4, 'little'))
            pos += len(s) + 1  # +1 for null byte
        for s in self.strings:
            f.write(s + b'\0')

    def __getitem__(self, item: int) -> str:
        """Get a string from the database"""
        return self.strings[item].decode(self.encoding, 'replace')

    def __delitem__(self, key: int):
        """Delete a string from the database"""
        del self.strings[key]

    def __setitem__(self, key: int, value: str | bytes):
        """Change a string in the database"""
        self.strings[key] = value if isinstance(value, bytes) else value.encode(self.encoding)

    def __iter__(self) -> Iterator[str]:
        """Iterate over the strings in the database"""
        for string in self.strings:
            yield string.decode(self.encoding, 'replace')

    def __len__(self) -> int:
        """Number of strings in the database"""
        return len(self.strings)

    def clear(self):
        self.strings = []

    def decode(self, data: bytes, stage_index: int) -> str:
        return data.decode(self.encoding, 'replace')

    def encode(self, string: str, stage_index: int) -> bytes:
        return string.encode(self.encoding)

    def iter_raw(self) -> Iterator[bytes]:
        """Iterate over the strings as raw (un-decoded) bytes"""
        yield from self.strings

    def iter_both(self) -> Iterator[tuple[bytes, str]]:
        """Iterate over the strings as both raw and decoded strings"""
        for string in self.strings:
            yield string, string.decode(self.encoding, 'replace')

    def append(self, string: str) -> int:
        """
        Append a string to the database

        :param string: The string to append to the database
        :return: The index of the appended string
        """
        new_index = len(self.strings)
        self.strings.append(string.encode(self.encoding))
        return new_index

    def insert(self, index: int, string: str) -> int:
        self.strings.insert(index, string.encode(self.encoding))
        return index

    def append_raw(self, string: bytes) -> int:
        """
        Append a raw byte string to the database with no encoding applied

        :param string: The byte string to append to the database
        :return: The index of the appended string
        """
        new_index = len(self.strings)
        self.strings.append(string)
        return new_index

    def get_by_id(self, string_id: int) -> str:
        return self[string_id]

    def get_index_from_id(self, string_id: int) -> int:
        return string_id

    def get_id_from_index(self, index: int) -> int:
        return index

    def iter_ids(self) -> Iterator[tuple[int, str]]:
        return enumerate(self)

    def iter_both_ids(self) -> Iterator[tuple[int, tuple[bytes, str]]]:
        return enumerate(self.iter_both())


class JapaneseStringDb(StringDb):
    BASIC = (
        ' .\u2bc8\u300c\u300d()\uff62\uff63\u201c\u201d\u2bc6012345'
        '6789:\u3001\u3002\u201d!? ABCDEFG'
        'HIJKLMNOPQRSTUVWXY'
        "Z[/]'ー\u00b7abcdefghijk"
        'lmnopqrstuvwxyzあいう'
        'えおかきくけこさしすせそたちつてとな'
        'にぬねのはひふへほまみむめもやゆよら'
        'りるれろわをんがぎぐげござじずぜぞだ'
        'ぢづでどばびぶべぼぱぴぷぺぽぁぃぅぇ'
        'ぉゃゅょっアイウエオカキクケコサシス'
        'セソタチツテトナニヌネノハヒフヘホマ'
        'ミムメモヤユヨラリルレロワヲンガギグ'
        'ゲゴザジズゼゾダヂヅデドバビブベボパ'
        'ピプペポァィゥェォャュョッヷ\u2e3a\u200b\0\0'
        '&\u2026+-#$%=          '
        '\0\0\0\0\0\0\0\0\u21e7\u21e9\u21e6\u21e8'
    )

    KANJI = [
        (
            '生命維持注射回復剤隔離病棟階地図医局'
            '員資料両親写真実験院長画像液体火薬冷'
            '凍室品庫発電機起動製工場双頭蛇眼球猿'
            '狼鷲設定書換源遮断向解除開戦避使事特'
            '何年制作月日時分足爆破血並差込口圧報'
            '告棚引出取入手配録力違外＊点決視変更'
            '始直座標目淮番号部屋移禁止終左右残度'
            '用御研究武器切調戻大懐感隣映監視減逃'
            '美女人誰側神抜版壊一倉箱具不気味意蔵'
            '細胞氷寒早巨拘束性必要通路障療空数字'
            '械別鉄格子廊下続思他死殺居前割化物警'
            '備念捕査助先行私僕名今憶呼聞見家帰過'
            '去脱君彼来話掛声殊務閉痛方法操返押線'
            '構成絵保育世界新創造主反応描供給装置'
            '補議怪立街灯胎児闘無傷覆落忘黒浮色路'
            '台着端末赤中灰皿自的仕頑丈山積扉鏡吹'
            '壁服配盤石'
        ),
        # TODO: transcribe remaining three kanji pages
        '',
        '',
        '',
    ]

    CODE_NAMES = {
        32769: 'r',
        32770: 'w',
        32771: 'p',
        32772: 'l',
        32773: 'y',
        32774: 'c',
    }

    NAME_CODES = {name: code for code, name in CODE_NAMES.items()}

    strings: list[bytes]

    def __init__(self, kanji_index: int = None):
        """Create a new Japanese string database with a given encoding"""
        self.strings = []
        self.kanji_index = kanji_index

    @property
    def suggested_extension(self) -> str:
        return '.JSD'

    @classmethod
    def sniff(cls, f: BinaryIO) -> Self | None:
        try:
            db = cls.read(f)
            # look for invalid characters
            if any(
                    0xff < code < 0x800
                    or 0x8ff < code < 0x8000
                    or (code & 0xc000 and (code & 0xff) > 6)
                    for string in db.iter_raw() for code in cls._unpack(string)
            ):
                return None
            return db
        except Exception:
            return None

    @staticmethod
    def _import_static(db: JapaneseStringDb, path: Path, kanji_index: int | None):
        strings = path.read_text(encoding='utf-8').split('\n')
        if strings[-1] == '':
            del strings[-1]
        for string in strings:
            db.append(string, kanji_index)

    def import_in_place(self, path: Path):
        self.clear()
        self._import_static(self, path, self.kanji_index)

    @classmethod
    def import_(cls, path: Path, fmt: str = None) -> Self:
        if fmt is None:
            fmt = '0'
        kanji_index = int(fmt)
        db = cls()
        cls._import_static(db, path, kanji_index)
        return db

    def export(self, path: Path, fmt: str = None) -> Path:
        if fmt is None:
            fmt = str(self.kanji_index) if self.kanji_index is not None else '0'
        kanji_index = int(fmt)
        new_path = path.with_suffix('.txt')
        with new_path.open('w', encoding='utf-8') as f:
            for string in self.strings:
                f.write(self.decode(string, kanji_index) + '\n')
        return new_path

    @classmethod
    def read(cls, f: BinaryIO, *, kanji_index: int = None, **kwargs) -> Self:
        """
        Read a string database file

        :param f: Binary data stream to read the string database from
        :param kanji_index: Index of the kanji set the strings were encoded for
        """
        db = cls(kanji_index)
        db.strings = f.read().split(b'\xff\xff')
        if len(db.strings) == 1:
            # there wasn't an FF FF delimiter anywhere in the file; this is probably wrong
            raise ValueError('The provided file does not appear to be a string database')
        if db.strings[-1] == b'':
            del db.strings[-1]
        return db

    def write(self, f: BinaryIO, **kwargs):
        """
        Write the strings in this object out to a database file

        :param f: Binary data stream to write the string database to
        """
        for s in self.strings:
            f.write(s + b'\xff\xff')

    @staticmethod
    def _unpack(data: bytes) -> list[int]:
        return list(struct.unpack(f'<{len(data) >> 1}H', data))

    @staticmethod
    def _pack(data: list[int]) -> bytes:
        return struct.pack(f'<{len(data)}H', *data)

    @classmethod
    def encode(cls, string: str, stage_index: int) -> bytes:
        out = []
        i = 0
        while i < len(string):
            c = string[i]
            if c == '$':
                i += 1
                str_code = string[i]
                if str_code in ['c', 'p', 'k', 'u']:
                    i += 1
                    if string[i] != '(':
                        raise ValueError(f'Expected ( after ${str_code}')
                    i += 1
                    end = string.index(')', i)
                    value = int(string[i:end])
                    i = end
                else:
                    value = None

                if str_code in cls.NAME_CODES:
                    code = cls.NAME_CODES[str_code]
                    if value is not None:
                        out.append(code)
                        code = value
                elif str_code == 'k':
                    code = value | 0x800
                elif str_code == '$':
                    code = cls.BASIC.index('$')
                elif str_code == 'u':
                    code = value
                else:
                    raise ValueError(f'Unknown control code {str_code}')
                out.append(code)
            elif c in cls.BASIC:
                out.append(cls.BASIC.index(c))
            else:
                out.append(cls.KANJI[stage_index].index(c) | 0x800)
            i += 1
        return cls._pack(out)

    @classmethod
    def decode(cls, data: bytes | list[int], stage_index: int, allow_unknown: bool = True) -> str:
        if isinstance(data, bytes):
            data = cls._unpack(data)
        out = ''
        expect_argument = False
        for code in data:
            if expect_argument:
                c = f'({code})'
                expect_argument = False
            elif code & 0xc000:
                if code in cls.CODE_NAMES:
                    c = '$' + cls.CODE_NAMES[code]
                else:
                    c = f'$u({code})'
                expect_argument = (code & 0xff) in [3, 6]
            else:
                if code & 0x800:
                    try:
                        c = cls.KANJI[stage_index][code & 0xff]
                    except IndexError:
                        if allow_unknown:
                            c = f'$k({code & 0xff})'
                        else:
                            raise
                else:
                    try:
                        c = cls.BASIC[code]
                        if c == '$':
                            c = '$$'  # escape
                    except IndexError:
                        if allow_unknown:
                            c = f'$u({code})'
                        else:
                            raise

            out += c
        return out

    def __getitem__(self, item: int) -> str:
        """Get a string from the database"""
        return self.decode(self.strings[item], self.kanji_index or 0)

    def __delitem__(self, key: int):
        """Delete a string from the database"""
        del self.strings[key]

    def __setitem__(self, key: int, value: list[int] | bytes | str):
        """Change a string in the database"""
        self.strings[key] = value if isinstance(value, bytes) else self._pack(value)

    def __iter__(self) -> Iterator[str]:
        """Iterate over the strings in the database"""
        for string in self.strings:
            yield self.decode(string, self.kanji_index or 0)

    def __len__(self) -> int:
        """Number of strings in the database"""
        return len(self.strings)

    def clear(self):
        self.strings = []

    def get_index_from_id(self, string_id: int) -> int:
        """Get a string's index in the database by its offset in the file"""
        for i, (current_id, s) in enumerate(self.iter_ids()):
            if current_id == string_id:
                return i
            if current_id > string_id:
                raise ValueError(f'{string_id} was not found')
        raise ValueError(f'{string_id} was not found')

    def get_id_from_index(self, index: int) -> int:
        """Get a string's offset in the file from its index in the database"""
        offset = 0
        for s in self.strings[:index]:
            offset += len(s)
        return offset

    def get_by_id(self, string_id: int) -> str:
        """Get a string from the database by its offset in the file"""
        return self[self.get_index_from_id(string_id)]

    def iter_both_ids(self) -> Iterator[tuple[int, tuple[bytes, str]]]:
        current = 0
        for s in self.strings:
            yield current, (s, self.decode(s, self.kanji_index or 0))
            current += len(s) + 2  # +2 for the delimiter

    def iter_ids(self) -> Iterator[tuple[int, str]]:
        for i, (_, s) in self.iter_both_ids():
            yield i, s

    def iter_raw(self) -> Iterator[bytes]:
        """Iterate over the strings as raw (un-decoded) bytes"""
        yield from self.strings

    def iter_both(self) -> Iterator[tuple[bytes, str]]:
        """Iterate over the strings as both raw and decoded strings"""
        for string in self.strings:
            yield string, self.decode(string, self.kanji_index or 0)

    def as_str(self, index: int, kanji_index: int = None) -> str:
        if kanji_index is None:
            kanji_index = self.kanji_index
        return self.decode(self.strings[index], kanji_index or 0)

    def append(self, string: str, kanji_index: int = None) -> int:
        """
        Append a string to the database

        :param string: The string to append to the database
        :param kanji_index: Index of the kanji set to use for encoding this string
        :return: The ID of the newly-appended string
        """
        if kanji_index is None:
            kanji_index = self.kanji_index
        new_index = len(self.strings)
        self.strings.append(self.encode(string, kanji_index or 0))
        return self.get_id_from_index(new_index)

    def insert(self, index: int, string: str, kanji_index: int = None) -> int:
        """
        Insert a string into the database at the given index

        :param index: The index at which to insert the string
        :param string: The string to insert into the database
        :param kanji_index: Index of the kanji set to use for encoding this string
        :return: The ID of the newly-inserted string
        """
        if kanji_index is None:
            kanji_index = self.kanji_index
        self.strings.insert(index, self.encode(string, kanji_index or 0))
        return self.get_id_from_index(index)

    def append_raw(self, string: bytes) -> int:
        """
        Append a raw byte string to the database with no encoding applied

        :param string: The byte string to append to the database
        :return: The ID of the newly-appended string
        """
        new_index = len(self.strings)
        self.strings.append(string)
        return self.get_id_from_index(new_index)


def pack(input_path: str, output_path: str, kanji_index: int | None):
    input_path = Path(input_path)
    if kanji_index is None:
        sdb = LatinStringDb.import_(input_path)
    else:
        sdb = JapaneseStringDb.import_(input_path, str(kanji_index))
    with open(output_path, 'wb') as f:
        sdb.write(f)


def unpack(input_path: str, output_path: str, kanji_index: int | None):
    with open(input_path, 'rb') as f:
        if kanji_index is None:
            sdb = LatinStringDb.read(f)
        else:
            sdb = JapaneseStringDb.read(f, kanji_index=kanji_index)
    sdb.export(Path(output_path))


def draw(font_path: str, kanji_index: int | None, db_path: str, target_path: str, indexes: list[int] | None,
         combine: bool):
    from galsdk.font import JapaneseFont, LatinFont

    font_path = Path(font_path)
    db_path = Path(db_path)
    target_path = Path(target_path)
    if kanji_index is not None:
        stage_index = kanji_index
        with db_path.open('rb') as f:
            db = JapaneseStringDb.read(f)
        font = JapaneseFont.load(font_path)
    else:
        stage_index = 0
        with db_path.open('rb') as f:
            db = LatinStringDb.read(f)
        font = LatinFont.load(font_path)

    if not indexes:
        indexes = list(range(len(db)))

    images = {}
    for index in indexes:
        images[index] = font.draw(db.strings[index], stage_index)

    if combine:
        from PIL import Image

        width = max(image.size[0] for image in images.values())
        height = sum(image.size[1] for image in images.values())
        new_image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        y = 0
        for image in images.values():
            new_image.paste(image, (0, y))
            y += image.size[1]
        new_image.save(target_path)
    else:
        for index, image in images.items():
            path = target_path
            if len(images) > 1:
                path = path.with_stem(path.stem + f'_{index}')
            image.save(path)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Pack or unpack Galerians string files')
    parser.add_argument('-j', '--japanese', type=int,
                        help='The string database is in Japanese. The argument to this option should be the index of '
                             'the kanji set to use for the strings.')
    subparsers = parser.add_subparsers(required=True)

    pack_parser = subparsers.add_parser('pack', help='Create a string database from a text file')
    pack_parser.add_argument('input', help='Text file to pack')
    pack_parser.add_argument('output', help='Path to string database to be created')
    pack_parser.set_defaults(action=lambda a: pack(a.input, a.output, a.japanese))

    unpack_parser = subparsers.add_parser('unpack', help='Unpack strings from a string database')
    unpack_parser.add_argument('input', help='Path to string database to be unpacked')
    unpack_parser.add_argument('output', help='Path to string file to be created')
    unpack_parser.set_defaults(action=lambda a: unpack(a.input, a.output, a.japanese))

    draw_parser = subparsers.add_parser('draw', help='Export images of strings rendered in the game font')
    draw_parser.add_argument('-c', '--combine', help='When exporting multiple strings, combine them into a single '
                             'image', action='store_true')
    draw_parser.add_argument('font', help='Path to the project directory whose font info to use')
    draw_parser.add_argument('db', help='Path to the string database to use')
    draw_parser.add_argument('target', help='Path to the image file(s) to be created. If exporting multiple images, '
                             'a numeric counter will be added to the end of the filename. The image format will be '
                             'detected from the file extension.')
    draw_parser.add_argument('indexes', type=int, nargs='*', help='If provided, specific indexes to draw from the '
                             'database. Otherwise, all entries will be drawn.')
    draw_parser.set_defaults(action=lambda a: draw(a.font, a.japanese, a.db, a.target, a.indexes, a.combine))

    args = parser.parse_args()
    args.action(args)
