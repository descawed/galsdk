import copy
import io
import os.path
import pathlib
from typing import BinaryIO, Container, Iterable, Self

from galsdk import util
from galsdk.format import FileFormat
from psx.tim import Tim


class GameTim(Tim, FileFormat):
    MAX_ITERATIONS = 10000

    def __init__(self):
        super().__init__()
        self.is_compressed = False

    @classmethod
    def decompress(cls, data: bytes) -> bytes:
        # not sure what this compression algorithm is, if it even is a well-known algorithm. it seems to take advantage
        # of the fact that the data being compressed doesn't contain all possible byte values, so it maps the unused
        # values to sequences of two values, which are recursively expanded. initially, all values are mapped to
        # themselves, so they would be output literally. the first part of the data encodes the mapped dictionary
        # sequences. the second part (starting from stream_len) is the actual compressed data.
        output = bytearray()
        with io.BytesIO(data) as f:
            data_len = util.int_from_bytes(f.read(4))
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

        return bytes(output)

    @staticmethod
    def compress(data: bytes) -> bytes:
        # the game only contains decompression code, not compression code, so I'm not totally sure how this should work.
        # I've played around with a few different attempts at a compressor, and they kind of work, but none of them
        # produce output that's even close to matching the original files. for now, we'll just fake it with an "empty"
        # dictionary followed by uncompressed data.
        output = len(data).to_bytes(2, 'big') + data
        # hard-coded empty dictionary (advance to index 0x80, store value 0x80, advance to index 0x100)
        output = b'\xff\x80\xfe' + output
        output = len(output).to_bytes(4, 'little') + output
        return output

    @classmethod
    def read_compressed(cls, source: BinaryIO) -> Self:
        data = cls.decompress(source.read())
        f = io.BytesIO(data)
        result = cls.read(f)
        result.is_compressed = True
        return result

    def write(self, destination: BinaryIO, with_compression: bool = None):
        if with_compression is None:
            with_compression = self.is_compressed
        if with_compression:
            f = io.BytesIO()
        else:
            f = destination
        super().write(f)
        if with_compression:
            destination.write(self.compress(f.read()))

    @property
    def suggested_extension(self) -> str:
        return '.TMC' if self.is_compressed else '.TIM'

    @classmethod
    def sniff(cls, f: BinaryIO) -> Self | None:
        try:
            return cls.read(f)
        except Exception:
            try:
                f.seek(0)
                return cls.read_compressed(f)
            except Exception:
                return None

    def export(self, path: pathlib.Path, fmt: str = None) -> pathlib.Path:
        if fmt is None:
            fmt = 'png'
        new_path = path.with_suffix(f'.{fmt}')
        self.to_image().save(str(new_path))
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


class TimDb(FileFormat):
    """
    A database of TIM images

    The game keeps TIM images for scene backgrounds and their associated masks in a combined database. This class reads
    and writes such databases.
    """

    images: list[GameTim]

    def __init__(self):
        """Create a new, empty TIM database"""
        self.images = []
        self.use_alternate_format = False

    def read(self, f: BinaryIO, with_compression: bool = False, use_alternate_format: bool = False):
        """
        Read a TIM database file

        :param f: Binary data stream to read the database file from
        :param with_compression: Whether the entries in the database file are compressed
        :param use_alternate_format: Whether the database file uses the alternate header format with offsets stored in
            number of words
        """
        self.images = []
        self.use_alternate_format = use_alternate_format
        num_images = util.int_from_bytes(f.read(4))
        if self.use_alternate_format:
            f.seek(0, 2)
            file_size = f.tell()
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
                self.images.append(GameTim.read_compressed(buf) if with_compression else GameTim.read(buf))

    def write(self, f: BinaryIO, with_compression: bool = None, use_alternate_format: bool = None):
        """
        Write the images in this object out to a database file

        :param f: Binary data stream to write the TIM database to
        :param with_compression: Whether the entries in the database file should be compressed
        :param use_alternate_format: Whether the database file should use the alternate header format with offsets
            stored in number of words. If None (the default), the format used when the database was read will be used.
            If None and the database has not been read, the alternate format will not be used.
        """
        raw_tims = []
        for image in self.images:
            with io.BytesIO() as buf:
                image.write(buf, with_compression)
                data = buf.getvalue()
                raw_tims.append(data)

        if use_alternate_format is None:
            use_alternate_format = self.use_alternate_format
        f.write(len(self.images).to_bytes(4, 'little'))
        if use_alternate_format:
            header_size = 0  # offsets are relative to end of header
        else:
            header_size = 4 + len(raw_tims)*8  # 2 32-bit integers per TIM
        offset = header_size
        for data in raw_tims:
            size = len(data)
            if use_alternate_format:
                f.write((offset // 4).to_bytes(4, 'little'))
            else:
                f.write(offset.to_bytes(4, 'little'))
                f.write(size.to_bytes(4, 'little'))
            offset += size
        for data in raw_tims:
            f.write(data)

    def __getitem__(self, item: int) -> GameTim:
        """Get an image from the database"""
        return self.images[item]

    def __setitem__(self, key: int, value: Tim):
        """Set an image in the database"""
        self.images[key] = GameTim.from_tim(value)

    def __iter__(self) -> Iterable[GameTim]:
        """Iterate over images in the database"""
        yield from self.images

    def __len__(self) -> int:
        """Number of images in the database"""
        return len(self.images)

    def append(self, image: Tim):
        """
        Add a new image to the database

        :param image: The TIM image to add to the database
        """
        self.images.append(GameTim.from_tim(image))

    @property
    def suggested_extension(self) -> str:
        if all(image.is_compressed for image in self.images):
            return '.TAC' if self.use_alternate_format else '.TDC'
        else:
            return '.TDA' if self.use_alternate_format else '.TDB'

    @classmethod
    def sniff(cls, f: BinaryIO) -> Self | None:
        try:
            # is it a regular TIM DB?
            db = cls()
            db.read(f)
            return db
        except Exception:
            pass

        f.seek(0)
        try:
            # is it a compressed TIM DB?
            db = cls()
            db.read(f, True)
            return db
        except Exception:
            pass

        f.seek(0)
        try:
            # is it an alternate TIM DB?
            db = cls()
            db.read(f, False, True)
            return db
        except Exception:
            pass

        f.seek(0)
        try:
            # is it a compressed alternate TIM DB?
            db = cls()
            db.read(f, True, True)
            return db
        except Exception:
            return None

    def export(self, path: pathlib.Path, fmt: str = None) -> pathlib.Path:
        if fmt is None:
            fmt = 'png'
        path.mkdir(exist_ok=True)
        for i, image in enumerate(self.images):
            image_path = path / str(i)
            if fmt == 'raw':
                with image_path.open('wb') as f:
                    image.write(f)
            else:
                image.export(image_path, fmt)
        return path


def pack(compressed: bool, files: Iterable[str], db_path: str):
    db = TimDb()
    for path in files:
        with open(path, 'rb') as f:
            db.append(Tim.read(f))
    with open(db_path, 'wb') as f:
        db.write(f, compressed)


def unpack(db_path: str, target: str, decompress: bool = False, indexes: Container[int] = None):
    db = TimDb()
    with open(db_path, 'rb') as f:
        db.read(f, decompress)
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
