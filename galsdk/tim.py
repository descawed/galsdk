import io
import os.path
from typing import BinaryIO, Container, Iterable

from psx.tim import Tim


class TimDb:
    """
    A database of TIM images

    The game keeps TIM images for scene backgrounds and their associated masks in a combined database. This class reads
    and writes such databases.
    """

    images: list[Tim]

    def __init__(self):
        """Create a new, empty TIM database"""
        self.images = []

    @staticmethod
    def decompress(data: bytes) -> bytes:
        # not sure what this compression algorithm is, if it even is a well-known algorithm. it seems to take advantage
        # of the fact that the data being compressed doesn't contain all possible byte values, so it maps the unused
        # values to sequences of two values, which are recursively expanded. initially, all values are mapped to
        # themselves, so they would be output literally. the first part of the data encodes the mapped dictionary
        # sequences. the second part (starting from stream_len) is the actual compressed data.
        output = bytearray()
        with io.BytesIO(data) as f:
            data_len = int.from_bytes(f.read(4), 'little')
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

                stream_len = int.from_bytes(f.read(2), 'big')
                end = f.tell() + stream_len
                while f.tell() != end:
                    stack = [f.read(1)[0]]
                    while len(stack) > 0:
                        index = stack.pop()
                        values = dictionary[index]
                        if values[0] == index:
                            output.append(values[0])
                        else:
                            stack.append(values[1])
                            stack.append(values[0])

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

    def read(self, f: BinaryIO, with_compression: bool = False):
        """
        Read a TIM database file

        :param f: Binary data stream to read the database file from
        :param with_compression: Whether the entries in the database file are compressed
        """
        self.images = []
        num_images = int.from_bytes(f.read(4), 'little')
        directory = [(int.from_bytes(f.read(4), 'little'), int.from_bytes(f.read(4), 'little'))
                     for _ in range(num_images)]
        for offset, size in directory:
            f.seek(offset)
            data = f.read(size)
            if with_compression:
                data = self.decompress(data)
            with io.BytesIO(data) as buf:
                self.images.append(Tim.read(buf))

    def write(self, f: BinaryIO, with_compression: bool = False):
        """
        Write the images in this object out to a database file

        :param f: Binary data stream to write the TIM database to
        :param with_compression: Whether the entries in the databse file should be compressed
        """
        raw_tims = []
        for image in self.images:
            with io.BytesIO() as buf:
                image.write(buf)
                data = buf.getvalue()
                if with_compression:
                    data = self.compress(data)
                raw_tims.append(data)

        f.write(len(self.images).to_bytes(4, 'little'))
        header_size = 4 + len(raw_tims)*8  # 2 32-bit integers per TIM
        offset = header_size
        for data in raw_tims:
            size = len(data)
            f.write(offset.to_bytes(4, 'little'))
            f.write(size.to_bytes(4, 'little'))
            offset += size
        for data in raw_tims:
            f.write(data)

    def __getitem__(self, item: int) -> Tim:
        """Get an image from the database"""
        return self.images[item]

    def __setitem__(self, key: int, value: Tim):
        """Set an image in the database"""
        self.images[key] = value

    def __iter__(self) -> Iterable[Tim]:
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
        self.images.append(image)


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
