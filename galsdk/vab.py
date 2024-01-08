from __future__ import annotations

from pathlib import Path
from typing import BinaryIO, Iterable, Self

from galsdk import file
from galsdk.format import Archive


class VabDb(Archive[bytes]):
    def __init__(self, vhs: list[bytes] = None, seqs: list[bytes] = None, vbs: list[bytes] = None,
                 use_alt_order: bool = False):
        super().__init__()
        self.vhs = vhs or []
        self.seqs = seqs or []
        self.vbs = vbs or []
        self.use_alt_order = use_alt_order

    @property
    def metadata(self) -> dict[str, bool | int | float | str | list | tuple | dict]:
        return {'use_alt_order': self.use_alt_order}

    @classmethod
    def from_metadata(cls, metadata: dict[str, bool | int | float | str | list | tuple | dict]) -> Self:
        return cls(use_alt_order=metadata['use_alt_order'])

    @property
    def files_with_type(self) -> Iterable[tuple[str, Iterable[bytes]]]:
        if self.use_alt_order:
            files_with_type = [('VH', self.vhs), ('SEQ', self.seqs), ('VB', self.vbs)]
        else:
            files_with_type = [('VB', self.vbs), ('VH', self.vhs), ('SEQ', self.seqs)]
        yield from files_with_type

    @classmethod
    def _read_alt(cls, f: BinaryIO) -> VabDb:
        # alternate format is VB + VH + SEQ just slapped together
        data = f.read()
        vh_count = data.count(b'pBAV')
        seq_count = data.count(b'pQES')
        # there's nothing we can search for to identify multiple VBs, so we only support one of each
        if vh_count != 1 or seq_count > 1:
            raise ValueError('Could not identify VAB database format')

        seq_offset = data.rfind(b'pQES')
        vh_offset = data.rfind(b'pBAV')
        if seq_offset == -1:
            seq_offset = len(data)
        elif seq_offset < vh_offset:
            # not the format we expected; bail
            raise ValueError('VAB database contents out-of-order for alternate format')
        vb = data[:vh_offset]
        vh = data[vh_offset:seq_offset]
        seq = data[seq_offset:]
        return cls([vh], [seq] if seq else [], [vb], True)

    @classmethod
    def read(cls, f: BinaryIO, **kwargs) -> VabDb:
        toc_len = int.from_bytes(f.read(4), 'little')
        # should be the length of the header section below, but sometimes it's not? just ignore it for now

        vh_len = file.int_from_bytes(f.read(4))
        vh_count = file.int_from_bytes(f.read(4))
        seq_len = file.int_from_bytes(f.read(4))
        seq_count = file.int_from_bytes(f.read(4))
        vb_len = file.int_from_bytes(f.read(4))
        vb_count = file.int_from_bytes(f.read(4), signed=True)

        if toc_len + vh_len + seq_len == 0 or vb_count <= 0:
            # try alternate read
            f.seek(0)
            return cls._read_alt(f)

        vh_offsets = []
        for i in range(vh_count):
            offset = file.int_from_bytes(f.read(4))
            if i == 0 or offset != 0:
                vh_offsets.append(offset)

        seq_offsets = []
        for _ in range(seq_count):
            offset = file.int_from_bytes(f.read(4))
            if offset != 0:
                seq_offsets.append(offset)

        vb_offsets = []
        for _ in range(vb_count):
            offset = file.int_from_bytes(f.read(4))
            if offset != 0:
                vb_offsets.append(offset)

        data_start = f.tell()
        all_offsets = sorted(vh_offsets + seq_offsets + vb_offsets)
        sizes = {}
        for i in range(len(all_offsets)):
            next_i = i + 1
            offset = all_offsets[i]
            if next_i >= len(all_offsets):
                sizes[offset] = vh_len + seq_len + vb_len - offset
            else:
                sizes[offset] = all_offsets[next_i] - offset

        vhs = []
        for offset in vh_offsets:
            size = sizes[offset]
            f.seek(data_start + offset)
            vhs.append(file.read_some(f, size))

        seqs = []
        for offset in seq_offsets:
            size = sizes[offset]
            f.seek(data_start + offset)
            seqs.append(file.read_some(f, size))

        vbs = []
        for offset in vb_offsets:
            size = sizes[offset]
            f.seek(data_start + offset)
            vbs.append(file.read_some(f, size))

        return cls(vhs, seqs, vbs)

    def _resolve_index(self, index: int) -> tuple[list[bytes], int, str]:
        if index >= len(self.vhs):
            index -= len(self.vhs)
            if index >= len(self.vbs):
                index -= len(self.vbs)
                return self.seqs, index, '.SEQ'
            return self.vbs, index, '.VB'
        return self.vhs, index, '.VH'

    def __getitem__(self, item: int) -> bytes:
        a, i, _ = self._resolve_index(item)
        return a[i]

    def __setitem__(self, key: int, value: bytes):
        a, i, _ = self._resolve_index(key)
        a[i] = value

    def __delitem__(self, key: int):
        a, i, _ = self._resolve_index(key)
        del a[i]

    def __len__(self) -> int:
        return len(self.vhs) + len(self.vbs) + len(self.seqs)

    def __iter__(self) -> Iterable[bytes]:
        yield from self.vhs
        yield from self.vbs
        yield from self.seqs

    def write(self, f: BinaryIO, **kwargs):
        if self.use_alt_order:
            # just raw data, no headers
            for vb in self.vbs:
                f.write(vb)
            for vh in self.vhs:
                f.write(vh)
            for seq in self.seqs:
                f.write(seq)
            return

        data = bytearray()
        vh_offsets = []
        seq_offsets = []
        vb_offsets = []

        for vh in self.vhs:
            vh_offsets.append(len(data))
            data.extend(vh)
        vh_len = len(data)

        for seq in self.seqs:
            seq_offsets.append(len(data))
            data.extend(seq)
        seq_len = len(data) - vh_len

        # SEQ count always matches VH count, so pad with 0 offsets where necessary
        extra_seqs = len(vh_offsets) - len(seq_offsets)
        if extra_seqs > 0:
            seq_offsets = ([0] * extra_seqs) + seq_offsets

        for vb in self.vbs:
            vb_offsets.append(len(data))
            data.extend(vb)
        vb_len = len(data) - seq_len - vh_len

        # always same number of entries
        f.write(b'\x18\0\0\0')
        f.write(vh_len.to_bytes(4, 'little'))
        f.write(len(vh_offsets).to_bytes(4, 'little'))
        f.write(seq_len.to_bytes(4, 'little'))
        f.write(len(seq_offsets).to_bytes(4, 'little'))
        f.write(vb_len.to_bytes(4, 'little'))
        f.write(len(vb_offsets).to_bytes(4, 'little'))

        for offset in vh_offsets + seq_offsets + vb_offsets:
            f.write(offset.to_bytes(4, 'little'))

        f.write(data)

    def append(self, item: bytes):
        if item[:4] == b'pBAV':
            self.vhs.append(item)
        elif item[:4] == b'pQES':
            self.seqs.append(item)
        else:
            self.vbs.append(item)

    def insert(self, index: int, item: bytes):
        if item[:4] == b'pBAV':
            self.vhs.insert(index, item)
        elif item[:4] == b'pQES':
            self.seqs.insert(index, item)
        else:
            self.vbs.insert(index, item)

    def append_raw(self, item: bytes):
        return self.append(item)

    @property
    def suggested_extension(self) -> str:
        return '.VDA' if self.use_alt_order else '.VDB'

    @property
    def supports_nesting(self) -> bool:
        return False

    def unpack_one(self, path: Path, index: int) -> Path:
        a, i, ext = self._resolve_index(index)
        new_path = path.with_suffix(ext)
        new_path.write_bytes(a[i])
        return new_path

    @classmethod
    def import_(cls, path: Path, fmt: str = None) -> Self:
        files = list(path.glob('*.VH')) + list(path.glob('*.VB')) + list(path.glob('*.SEQ'))
        return cls.import_explicit(files, fmt)

    @classmethod
    def import_explicit(cls, paths: Iterable[Path], fmt: str = None) -> Self:
        use_alt_order = fmt == 'alt'
        vhs = []
        vbs = []
        seqs = []

        for path in paths:
            data = path.read_bytes()
            match path.suffix.lower():
                case '.vh':
                    assert data[:4] == b'pBAV'
                    vhs.append(data)
                case '.vb':
                    vbs.append(data)
                case '.seq':
                    assert data[:4] == b'pQES'
                    seqs.append(data)
                case _:
                    raise ValueError('Unknown file type encountered while importing VAB DB')

        return cls(vhs, seqs, vbs, use_alt_order)

    def export(self, path: Path, fmt: str = None) -> Path:
        path.mkdir(exist_ok=True)
        for i, vh in enumerate(self.vhs):
            (path / f'{i:03}').with_suffix('.VH').write_bytes(vh)
        for i, vb in enumerate(self.vbs):
            (path / f'{i:03}').with_suffix('.VB').write_bytes(vb)
        for i, seq in enumerate(self.seqs):
            (path / f'{i:03}').with_suffix('.SEQ').write_bytes(seq)
        return path


def pack(db_path: str, files: list[str], use_alternate_format: bool):
    db = VabDb.import_explicit((Path(filename) for filename in files), 'alt' if use_alternate_format else None)
    with open(db_path, 'wb') as f:
        db.write(f)


def unpack(db_path: str, out_path: str):
    with open(db_path, 'rb') as f:
        db = VabDb.read(f)
    db.export(Path(out_path))


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Pack or unpack Galerians VAB databases')
    subparsers = parser.add_subparsers()

    pack_parser = subparsers.add_parser('pack', help='Create a VAB DB from a list of files')
    pack_parser.add_argument('-a', '--alternate', help='Use the alternate format with no header')
    pack_parser.add_argument('db', help='Path to VAB DB to be created')
    pack_parser.add_argument('files', nargs='+', help='One or more files to include in the database. This command uses '
                             'the file extension to determine the file type; valid extensions are .VH, .VB, and .SEQ.')
    pack_parser.set_defaults(action=lambda a: pack(a.db, a.files, a.alternate))

    unpack_parser = subparsers.add_parser('unpack', help='Unpack files from a VAB DB into a directory')
    unpack_parser.add_argument('db', help='Path to VAB DB to be unpacked')
    unpack_parser.add_argument('target', help='Path to directory where files will be unpacked')
    unpack_parser.set_defaults(action=lambda a: unpack(a.db, a.target))

    args = parser.parse_args()
    args.action(args)
