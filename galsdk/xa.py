from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, ByteString, Iterable, Self

import ffmpeg

from galsdk import util
from galsdk.format import Archive
from galsdk.media import Media
from psx.cd.disc import Sector, SubMode


class XaAudio(Media):
    def __init__(self, path: Path):
        super().__init__(path, 'wav')

    def convert(self, playable_path: Path):
        ffmpeg.input(str(self.path), format='psxstr').audio.output(str(playable_path)).run()


@dataclass
class XaRegion:
    channel: int
    start: int
    end: int
    data: bytes = None

    def convert(self, fmt: str) -> bytes:
        if self.data is None:
            raise ValueError("Region's data is not set")

        process = (
            ffmpeg.input('pipe:', format='psxstr').audio
            .output('pipe:', format=fmt)
            .run_async(pipe_stdin=True, pipe_stdout=True)
        )
        out, _ = process.communicate(input=self.data)
        output = bytearray()
        while data := process.stdout.read():
            output.extend(data)
        process.wait()
        return bytes(output)

    def as_str(self) -> str:
        return f'{self.channel} {self.start} {self.end}'


class XaDatabase(Archive[bytes]):
    MAGIC = b'\x41\x89'

    def __init__(self, regions: list[XaRegion] = None, data: ByteString = None):
        self.regions = regions or []
        if data is not None:
            self.set_data(data)

    def set_data(self, data: ByteString):
        if len(data) % Sector.SIZE != 0:
            raise ValueError('XA data appears incomplete')

        for region in self.regions:
            sector_data = bytearray()
            for i in range(region.start, region.end+1):
                start = i*Sector.SIZE
                # FIXME: some regions ask for sectors a couple past the end of XA.MXA. this probably means that we need
                #  to grab some extra sectors past the end of where the filesystem says it ends.
                if start >= len(data):
                    break
                sector = Sector(data[start:(i+1)*Sector.SIZE])
                if sector.channel != region.channel:
                    # zero out other channels
                    sector.sub_mode = SubMode.DATA
                    sector.data[:] = bytes(sector.data_size)
                sector_data.extend(sector.raw)
            region.data = sector_data

    def __getitem__(self, item: int) -> bytes:
        return self.regions[item].data

    def __setitem__(self, key: int, value: bytes):
        region = self.regions[key]
        first_sector = Sector(value[:Sector.SIZE])
        region.channel = first_sector.channel
        if region.channel is None:
            raise ValueError('Not a valid XA sector')
        region.data = value

    def __delitem__(self, key: int):
        del self.regions[key]

    def __len__(self) -> int:
        return len(self.regions)

    def __iter__(self) -> Iterable[bytes]:
        for region in self.regions:
            yield region.data

    def append(self, item: bytes | Self):
        raise NotImplementedError

    @classmethod
    def read(cls, f: BinaryIO, **kwargs) -> XaDatabase:
        magic = f.read(2)
        if magic != cls.MAGIC:
            raise ValueError('Not an XA database')

        num_entries = util.int_from_bytes(f.read(2))
        regions = []
        for _ in range(num_entries):
            channel = util.int_from_bytes(f.read(4))
            start = util.int_from_bytes(f.read(4))
            end = util.int_from_bytes(f.read(4))
            regions.append(XaRegion(channel, start, end))

        return cls(regions)

    def write(self, f: BinaryIO, **kwargs):
        f.write(self.MAGIC)
        f.write(len(self.regions).to_bytes(2, 'little'))
        for region in self.regions:
            f.write(region.channel.to_bytes(4, 'little'))
            f.write(region.start.to_bytes(4, 'little'))
            f.write(region.end.to_bytes(4, 'little'))

    @property
    def is_ready(self) -> bool:
        return all(region.data for region in self.regions)

    @property
    def suggested_extension(self) -> str:
        return '.XDB'

    @property
    def supports_nesting(self) -> bool:
        return False

    @classmethod
    def sniff(cls, f: BinaryIO) -> Self | None:
        try:
            return cls.read(f)
        except Exception:
            return None

    def unpack_one(self, path: Path, index: int) -> Path:
        region = self.regions[index]
        if region.data:
            path.write_bytes(region.data)
        else:
            raise ValueError('Attempted to unpack an XA database entry with no data set')
        return path

    @classmethod
    def import_(cls, path: Path, fmt: str = None) -> Self:
        raise NotImplementedError

    @classmethod
    def import_explicit(cls, paths: Iterable[Path], fmt: str = None) -> Self:
        raise NotImplementedError

    def export(self, path: Path, fmt: str = None) -> Path:
        path.mkdir(exist_ok=True)
        if self.is_ready:
            for i, region in enumerate(self.regions):
                (path / f'{i:003}.XA').write_bytes(region.data)
        else:
            raise ValueError('Attempted to export an XA database with no data set')
        return path
