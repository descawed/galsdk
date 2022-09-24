from typing import BinaryIO, Iterable


# we keep everything as bytes internally because there are some cases where there are bogus characters in the data
# that we don't want to overwrite unless requested
class StringDb:
    """
    A database of text strings used within a game stage

    The game keeps the message strings for each stage in one database file per stage. These databases are similar to
    but not the same as the CDB database files; each entry is a single null-terminated string rather than a file.
    Strings are referenced in code by their index in these databases.
    """
    MAGIC = b'\x41\x84'

    strings: list[bytes]

    def __init__(self, encoding: str = 'windows-1252'):
        """
        Create a new string database with a given encoding

        :param encoding: Character encoding to use for strings in the database
        """
        self.strings = []
        self.encoding = encoding

    def read(self, f: BinaryIO):
        """
        Read a string database file

        :param f: Binary data stream to read the string databse from
        """
        self.strings = []
        magic = f.read(2)
        if magic != self.MAGIC:
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
            self.strings.append(data)

    def write(self, f: BinaryIO):
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

    def __setitem__(self, key: int, value: str):
        """Change a string in the database"""
        self.strings[key] = value.encode(self.encoding)

    def __iter__(self) -> Iterable[str]:
        """Iterate over the strings in the database"""
        for string in self.strings:
            yield string.decode(self.encoding, 'replace')

    def __len__(self) -> int:
        """Number of strings in the database"""
        return len(self.strings)

    def iter_raw(self) -> Iterable[bytes]:
        """Iterate over the strings as raw (un-decoded) bytes"""
        yield from self.strings

    def iter_both(self) -> Iterable[tuple[bytes, str]]:
        """Iterate over the strings as both raw and decoded strings"""
        for string in self.strings:
            yield string, string.decode(self.encoding, 'replace')

    def append(self, string: str):
        """
        Append a string to the database

        :param string: The string to append to the database
        """
        self.strings.append(string.encode(self.encoding))

    def append_raw(self, string: bytes):
        """
        Append a raw byte string to the database with no encoding applied

        :param string: The byte string to append to the database
        """
        self.strings.append(string)


def pack(input_path: str, output_path: str):
    sdb = StringDb()
    with open(input_path, 'rb') as f:
        s = b''
        while c := f.read(1):
            if c == b'\n':
                sdb.append(s)
                s = b''
            else:
                s += c
        if s:
            sdb.append_raw(s)
    with open(output_path, 'wb') as f:
        sdb.write(f)


def unpack(input_path: str, output_path: str):
    sdb = StringDb()
    with open(input_path, 'rb') as f:
        sdb.read(f)
    with open(output_path, 'wb') as f:
        for string in sdb.iter_raw():
            f.write(string + b'\n')


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Pack or unpack Galerians string files')
    subparsers = parser.add_subparsers()

    pack_parser = subparsers.add_parser('pack', help='Create a string database from a text file')
    pack_parser.add_argument('input', help='Text file to pack (must use LF line endings, not CRLF)')
    pack_parser.add_argument('output', help='Path to string database to be created')
    pack_parser.set_defaults(action=lambda a: pack(a.input, a.output))

    unpack_parser = subparsers.add_parser('unpack', help='Unpack strings from a string database')
    unpack_parser.add_argument('input', help='Path to string database to be unpacked')
    unpack_parser.add_argument('output', help='Path to string file to be created')
    unpack_parser.set_defaults(action=lambda a: unpack(a.input, a.output))

    args = parser.parse_args()
    args.action(args)
