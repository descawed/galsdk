from __future__ import annotations

from typing import BinaryIO, Iterable


class VabDb:
    def __init__(self, vhs: list[bytes], seqs: list[bytes], vbs: list[bytes], use_alt_order: bool = False):
        self.vhs = vhs
        self.seqs = seqs
        self.vbs = vbs
        self.use_alt_order = use_alt_order

    @property
    def files_with_type(self) -> Iterable[tuple[str, Iterable[bytes]]]:
        if self.use_alt_order:
            files_with_type = [('VH', self.vhs), ('SEQ', self.seqs), ('VB', self.vbs)]
        else:
            files_with_type = [('VB', self.vbs), ('VH', self.vhs), ('SEQ', self.seqs)]
        yield from files_with_type

    @classmethod
    def _read_alt(cls, f: BinaryIO) -> VabDb | None:
        # alternate format is VB + VH + SEQ just slapped together
        data = f.read()
        vh_count = data.count(b'pBAV')
        seq_count = data.count(b'pQES')
        # there's nothing we can search for to identify multiple VBs, so we only support one of each
        if vh_count != 1 or seq_count > 1:
            return None

        seq_offset = data.rfind(b'pQES')
        vh_offset = data.rfind(b'pBAV')
        if seq_offset == -1:
            seq_offset = len(data)
        elif seq_offset < vh_offset:
            # not the format we expected; bail
            return None
        vb = data[:vh_offset]
        vh = data[vh_offset:seq_offset]
        seq = data[seq_offset:]
        return cls([vh], [seq] if seq else [], [vb], True)

    @classmethod
    def read(cls, f: BinaryIO) -> VabDb | None:
        toc_len = int.from_bytes(f.read(4), 'little')
        # should be the length of the header section below, but sometimes it's not? just ignore it for now

        vh_len = int.from_bytes(f.read(4), 'little')
        vh_count = int.from_bytes(f.read(4), 'little')
        seq_len = int.from_bytes(f.read(4), 'little')
        seq_count = int.from_bytes(f.read(4), 'little')
        vb_len = int.from_bytes(f.read(4), 'little')
        vb_count = int.from_bytes(f.read(4), 'little', signed=True)

        if toc_len + vh_len + seq_len == 0 or vb_count <= 0:
            # try alternate read
            f.seek(0)
            return cls._read_alt(f)

        vh_offsets = []
        for i in range(vh_count):
            offset = int.from_bytes(f.read(4), 'little')
            if i == 0 or offset != 0:
                vh_offsets.append(offset)

        seq_offsets = []
        for _ in range(seq_count):
            offset = int.from_bytes(f.read(4), 'little')
            if offset != 0:
                seq_offsets.append(offset)

        vb_offsets = []
        for _ in range(vb_count):
            offset = int.from_bytes(f.read(4), 'little')
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
            vhs.append(f.read(size))

        seqs = []
        for offset in seq_offsets:
            size = sizes[offset]
            f.seek(data_start + offset)
            seqs.append(f.read(size))

        vbs = []
        for offset in vb_offsets:
            size = sizes[offset]
            f.seek(data_start + offset)
            vbs.append(f.read(size))

        return cls(vhs, seqs, vbs)

    def write(self, f: BinaryIO):
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
