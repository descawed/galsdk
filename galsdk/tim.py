from __future__ import annotations

import copy
import io
import os.path
from enum import Enum, auto
from pathlib import Path
from typing import BinaryIO, Container, Iterable, Self

from PIL import Image

from galsdk import util
from galsdk.format import Archive, FileFormat
from psx.tim import Tim


class TimFormat(Tim, FileFormat):
    @property
    def suggested_extension(self) -> str:
        return '.TIM'

    @classmethod
    def sniff(cls, f: BinaryIO) -> Self | None:
        try:
            return cls.read(f)
        except Exception:
            return None

    @classmethod
    def import_(cls, path: Path, fmt: str = None) -> Self:
        if fmt is None:
            fmt = path.suffix
            if not fmt:
                fmt = 'tim'
            if fmt[0] == '.':
                fmt = fmt[1:]
        fmt = fmt.lower()

        if fmt in ['tim', 'raw']:
            with path.open('rb') as f:
                return cls.read(f)

        return cls.from_image(Image.open(path, 'r', [fmt]))

    def export(self, path: Path, fmt: str = None) -> Path:
        if fmt is None:
            fmt = 'png'
        if fmt.lower() in ['raw', 'tim']:
            new_path = path.with_suffix('.TIM')
            with new_path.open('wb') as f:
                self.write(f)
        else:
            new_path = path.with_suffix(f'.{fmt}')
            self.to_image().save(new_path)
        return new_path

    @classmethod
    def from_tim(cls, tim: Tim) -> Self:
        if isinstance(tim, cls):
            return tim
        new = cls()
        new.raw_clut_bounds = tim.raw_clut_bounds
        new.raw_image_bounds = tim.raw_image_bounds
        new.palettes = copy.deepcopy(tim.palettes)
        new.image_data = tim.image_data
        new.width = tim.width
        new.height = tim.height
        new.bpp = tim.bpp
        return new


class TimDb(Archive[Tim]):
    """
    A database of TIM images

    The game keeps TIM images for scene backgrounds and their associated masks in a combined database. This class reads
    and writes such databases.
    """
    class Format(Enum):
        DEFAULT = auto()
        ALTERNATE = auto()
        COMPRESSED_DB = auto()
        COMPRESSED_STREAM = auto()
        STREAM = auto()

        @classmethod
        def from_extension(cls, extension: str) -> Self | None:
            if extension[0] == '.':
                extension = extension[1:]
            match extension.lower():
                case 'tdb':
                    return cls.DEFAULT
                case 'tda':
                    return cls.ALTERNATE
                case 'tdc':
                    return cls.COMPRESSED_DB
                case 'tmc':
                    return cls.COMPRESSED_STREAM
                case 'tmm':
                    return cls.STREAM
            return None

    MAX_ITERATIONS = 10000

    images: list[TimFormat | TimDb]

    def __init__(self, fmt: Format = Format.DEFAULT):
        """Create a new, empty TIM database"""
        self.images = []
        self.offsets = {}
        self.format = fmt

    @classmethod
    def decompress(cls, data: bytes) -> list[tuple[int, bytes]]:
        # not sure what this compression algorithm is, if it even is a well-known algorithm. it seems to take advantage
        # of the fact that the data being compressed doesn't contain all possible byte values, so it maps the unused
        # values to sequences of two values, which are recursively expanded. initially, all values are mapped to
        # themselves, so they would be output literally. the first part of the data encodes the mapped dictionary
        # sequences. the second part (starting from stream_len) is the actual compressed data.
        results = []
        stream_end = len(data)
        with io.BytesIO(data) as f:
            while f.tell() < stream_end:
                offset = f.tell()
                output = bytearray()
                data_len = util.int_from_bytes(f.read(4))
                if data_len == 0:
                    break
                if data_len > stream_end - f.tell():
                    raise EOFError('EOF encountered while decompressing TIM')
                data_end = f.tell() + data_len
                while f.tell() < data_end:
                    dictionary = [(i, None) for i in range(0x100)]
                    index = 0
                    while index != 0x100:
                        # we select an index into the dictionary and/or a number of entries to update
                        byte = f.read(1)[0]
                        if byte < 0x80:
                            # if byte < 0x80, the loop below will iterate from index:index+byte
                            count = byte + 1
                        else:
                            # otherwise, we update our dictionary index and perform only a single loop
                            index += byte - 0x7f
                            count = 1

                        for _ in range(count):
                            if index == 0x100:
                                break
                            byte = f.read(1)[0]
                            dictionary[index] = (byte, None)
                            if byte != index:
                                dictionary[index] = (byte, f.read(1)[0])
                            index += 1

                    stream_len = util.int_from_bytes(f.read(2), 'big')
                    end = f.tell() + stream_len
                    while f.tell() != end:
                        stack = [f.read(1)[0]]
                        i = 0
                        while len(stack) > 0:
                            index = stack.pop()
                            values = dictionary[index]
                            if values[0] == index:
                                output.append(values[0])
                            else:
                                stack.append(values[1])
                                stack.append(values[0])
                            i += 1
                            if i > cls.MAX_ITERATIONS:
                                raise RuntimeError('The decompression routine appears to be stuck in an infinite loop')
                results.append((offset, bytes(output)))
                # data is padded out to a multiple of 4 with '0' characters
                padding_needed = (4 - data_len & 3) & 3
                if padding_needed > 0:
                    padding = f.read(padding_needed)
                    if not all(c in [0, 0x30] for c in padding):
                        raise ValueError('Expected padding bytes')

        return results

    @staticmethod
    def compress(data: bytes) -> bytes:
        # the game only contains decompression code, not compression code, so I'm not totally sure how this should work.
        # I've played around with a few different attempts at a compressor, and they kind of work, but none of them
        # produce output that's even close to matching the original files. for now, we'll just fake it with an "empty"
        # dictionary followed by uncompressed data.
        output = len(data).to_bytes(2, 'big') + data
        # hard-coded empty dictionary (advance to index 0x80, store value 0x80, advance to index 0x100)
        output = b'\xff\x80\xfe' + output
        data_len = len(output)
        padding_needed = (4 - data_len & 3) & 3
        if padding_needed > 0:
            output += b'0' * padding_needed
        output = data_len.to_bytes(4, 'little') + output
        return output

    @classmethod
    def read(cls, f: BinaryIO, *, fmt: Format = Format.DEFAULT, **kwargs) -> Self:
        """
        Read a TIM database file

        :param f: Binary data stream to read the database file from
        :param fmt: Format of the TIM database
        """
        db = cls(fmt)
        if fmt == cls.Format.COMPRESSED_STREAM:
            for offset, data in cls.decompress(f.read()):
                db.append(TimFormat.read_bytes(data), offset)
            return db
        file_size = f.seek(0, 2)
        f.seek(0)
        if fmt == cls.Format.STREAM:
            while f.tell() < file_size:
                # this is a bit of a hack because it relies on TimFormat not doing absolute seeks
                db.append(TimFormat.read(f))
                # skip any padding or zeroes at the end of the file
                while (last_char := f.read(1)) in [b'\0', b'0']:
                    pass
                if last_char != b'':
                    f.seek(-1, 1)
            return db

        num_images = util.int_from_bytes(f.read(4))
        if fmt == cls.Format.ALTERNATE:
            f.seek(4)
            header_size = (num_images + 1) * 4  # +1 for the image count itself
            directory = [(header_size + util.int_from_bytes(f.read(4)) * 4, 0) for _ in range(num_images)]
            for i in range(num_images):
                offset = directory[i][0]
                if i + 1 < num_images:
                    directory[i] = (offset, directory[i + 1][0] - offset)
                else:
                    directory[i] = (offset, file_size - offset)
        else:
            directory = [(util.int_from_bytes(f.read(4)), util.int_from_bytes(f.read(4)) & 0xffffff)
                         for _ in range(num_images)]
        for offset, size in directory:
            f.seek(offset)
            data = util.read_some(f, size)
            with io.BytesIO(data) as buf:
                if fmt == cls.Format.COMPRESSED_DB:
                    sub_db = cls.read(buf, fmt=cls.Format.COMPRESSED_STREAM)
                    db.append(sub_db, offset)
                else:
                    db.append(TimFormat.read(buf), offset)

        return db

    def write(self, f: BinaryIO, *, fmt: Format = None, **kwargs):
        """
        Write the images in this object out to a database file

        :param f: Binary data stream to write the TIM database to
        :param fmt: Format to save the TIM database in
        """
        if fmt is None:
            fmt = self.format

        raw_tims = []
        self.offsets = {}
        for image in self.images:
            with io.BytesIO() as buf:
                image.write(buf)
                data = buf.getvalue()
                if fmt in [self.Format.COMPRESSED_DB, self.Format.COMPRESSED_STREAM] and isinstance(image, Tim):
                    data = self.compress(data)
                raw_tims.append(data)

        if fmt not in [self.Format.COMPRESSED_STREAM, self.Format.STREAM]:
            f.write(len(self.images).to_bytes(4, 'little'))
            if fmt == self.Format.ALTERNATE:
                header_size = 0  # offsets are relative to end of header
            else:
                header_size = 4 + len(raw_tims)*8  # 2 32-bit integers per TIM
            offset = header_size
            for data in raw_tims:
                size = len(data)
                if fmt == self.Format.ALTERNATE:
                    f.write((offset // 4).to_bytes(4, 'little'))
                else:
                    f.write(offset.to_bytes(4, 'little'))
                    f.write(size.to_bytes(4, 'little'))
                offset += size
        for i, data in enumerate(raw_tims):
            self.offsets[f.tell()] = i
            f.write(data)

    def __getitem__(self, item: int) -> TimFormat | TimDb:
        """Get an image from the database"""
        return self.images[item]

    def __setitem__(self, key: int, value: Tim | TimDb):
        """Set an image in the database"""
        if isinstance(value, Tim):
            value = TimFormat.from_tim(value)
        self.images[key] = TimFormat.from_tim(value)

    def __delitem__(self, key: int):
        del self.images[key]

    def __iter__(self) -> Iterable[TimFormat | TimDb]:
        """Iterate over the contents of the database"""
        yield from self.images

    def __len__(self) -> int:
        """Number of images in the database"""
        return len(self.images)

    def get_index_from_offset(self, offset: int) -> int:
        return self.offsets[offset]

    def append(self, image: Tim | TimDb, offset: int = None):
        """
        Add a new image to the database

        :param image: The TIM image to add to the database
        :param offset: The offset the TIM was located at in the database.
        """
        if isinstance(image, Tim):
            image = TimFormat.from_tim(image)
        if offset is not None:
            self.offsets[offset] = len(self.images)
        self.images.append(image)

    @property
    def suggested_extension(self) -> str:
        match self.format:
            case self.Format.DEFAULT:
                return '.TDB'
            case self.Format.ALTERNATE:
                return '.TDA'
            case self.Format.COMPRESSED_DB:
                return '.TDC'
            case self.Format.COMPRESSED_STREAM:
                return '.TMC'
            case self.Format.STREAM:
                return '.TMM'

    @property
    def supports_nesting(self) -> bool:
        return True

    @classmethod
    def sniff(cls, f: BinaryIO) -> Self | None:
        try:
            # is it a regular TIM DB?
            return cls.read(f)
        except Exception:
            pass

        f.seek(0)
        try:
            # is it a compressed TIM DB?
            return cls.read(f, fmt=cls.Format.COMPRESSED_DB)
        except Exception:
            pass

        f.seek(0)
        try:
            # is it an alternate TIM DB?
            return cls.read(f, fmt=cls.Format.ALTERNATE)
        except Exception:
            pass

        f.seek(0)
        try:
            # is it a compressed TIM stream?
            return cls.read(f, fmt=cls.Format.COMPRESSED_STREAM)
        except Exception:
            pass

        f.seek(0)
        try:
            # is it an uncompressed TIM stream?
            db = cls.read(f, fmt=cls.Format.STREAM)
            if len(db) == 1:
                # an uncompressed TIM stream of length 1 is just a TIM
                return None
            return db
        except Exception:
            return None

    def unpack_one(self, path: Path, index: int) -> Path:
        item = self.images[index]
        if isinstance(item, TimDb):
            new_path = path.with_suffix(item.suggested_extension)
            with new_path.open('wb') as f:
                item.write(f, fmt=self.Format.from_extension(item.suggested_extension))
            return new_path

        new_path = path.with_suffix('.TIM')
        with new_path.open('wb') as f:
            item.write(f)
        return new_path

    @classmethod
    def import_(cls, path: Path, fmt: str = None) -> Self:
        if fmt is None:
            fmt = path.suffix or None
        return cls.import_explicit(path.iterdir(), fmt)

    @classmethod
    def import_explicit(cls, paths: Iterable[Path], fmt: str = None) -> Self:
        if fmt is None:
            fmt = 'tdb'

        fmt = fmt.lower()
        if fmt[0] == '.':
            fmt = fmt[1:]
        is_stream = False
        match fmt:
            case 'tdb':
                db_fmt = cls.Format.DEFAULT
            case 'tda':
                db_fmt = cls.Format.ALTERNATE
            case 'tdc':
                db_fmt = cls.Format.COMPRESSED_DB
            case 'tmc':
                db_fmt = cls.Format.COMPRESSED_STREAM
                is_stream = True
            case 'tmm':
                db_fmt = cls.Format.STREAM
                is_stream = True
            case _:
                raise ValueError(f'Unknown TIM DB format {fmt}')

        db = cls(db_fmt)
        for path in paths:
            if path.is_dir() or path.suffix.lower() in ['.tmc', '.tmm']:
                if is_stream:
                    raise ValueError('A TIM stream should not contain another TIM stream')
                if path.is_dir():
                    db.append(cls.import_(path, path.suffix or 'tmc'))
                else:
                    with path.open('rb') as f:
                        db.append(cls.read(f, fmt=cls.Format.COMPRESSED_STREAM))
            else:
                db.append(TimFormat.import_(path))

        return db

    def export(self, path: Path, fmt: str = None) -> Path:
        if fmt is None:
            fmt = 'png'
        num_images = len(self.images)
        if num_images > 1:
            path.mkdir(exist_ok=True)
        for i, image in enumerate(self.images):
            if num_images > 1:
                image_path = path / f'{i:03}'
            else:
                image_path = path
            new_path = image.export(image_path, fmt)
            if num_images == 1:
                return new_path
        return path


def pack(compressed: bool, files: Iterable[str], db_path: str):
    db = TimDb()
    for path in files:
        with open(path, 'rb') as f:
            db.append(Tim.read(f))
    with open(db_path, 'wb') as f:
        db.write(f, fmt=TimDb.Format.COMPRESSED_DB if compressed else TimDb.Format.DEFAULT)


def unpack(db_path: str, target: str, decompress: bool = False, indexes: Container[int] = None):
    db = TimDb()
    with open(db_path, 'rb') as f:
        db.read(f, fmt=TimDb.Format.COMPRESSED_DB if decompress else TimDb.Format.DEFAULT)
    for i, tim in enumerate(db):
        if indexes and i not in indexes:
            continue
        output_path = os.path.join(target, f'{i}.TIM')
        with open(output_path, 'wb') as f:
            tim.write(f)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Pack or unpack Galerians TIM database files')
    subparsers = parser.add_subparsers()

    pack_parser = subparsers.add_parser('pack', help='Create a TIM DB from a list of files')
    pack_parser.add_argument('-c', '--compress',
                             help='Compress the files in the database', action='store_true')
    pack_parser.add_argument('db', help='Path to TIM DB to be created')
    pack_parser.add_argument('files', nargs='+', help='One or more files to include in the database')
    pack_parser.set_defaults(action=lambda a: pack(a.compress, a.files, a.db))

    unpack_parser = subparsers.add_parser('unpack', help='Unpack files from a TIM DB into a directory')
    unpack_parser.add_argument('-d', '--decompress',
                               help='The files in the database are compressed; decompress them', action='store_true')
    unpack_parser.add_argument('db', help='Path to TIM DB to be unpacked')
    unpack_parser.add_argument('target', help='Path to directory where files will be unpacked')
    unpack_parser.add_argument('indexes', nargs='*', type=int, help='One or more indexes to extract from the database. '
                               'If not provided, all files in the database will be extracted')
    unpack_parser.set_defaults(action=lambda a: unpack(a.db, a.target, a.decompress, set(a.indexes)))

    args = parser.parse_args()
    args.action(args)
