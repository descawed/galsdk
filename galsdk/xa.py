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

    @property
    def first_audio_sector(self) -> int:
        for i in range(0, len(self.data), Sector.SIZE):
            sector = Sector(self.data[i:i + Sector.SIZE])
            if sector.sub_mode & SubMode.AUDIO:
                return i // Sector.SIZE
        return 0


class XaDatabase(Archive[bytes]):
    MAGIC = b'\x41\x89'

    def __init__(self, regions: list[XaRegion] = None, data: ByteString = None):
        super().__init__()
        self.regions = regions or []
        if data is not None:
            self.set_data(data)

    def set_data(self, data: ByteString):
        if len(data) % Sector.SIZE != 0:
            raise ValueError('XA data appears incomplete')

        self.clean_regions(data)

    def clean_regions(self, data: ByteString = None):
        for region in self.regions:
            input_data = region.data if data is None else data
            sector_data = bytearray()
            for i in range(region.start, region.end + 1):
                start = i * Sector.SIZE
                # FIXME: some regions ask for sectors a couple past the end of XA.MXA. this probably means that we need
                #  to grab some extra sectors past the end of where the filesystem says it ends.
                if start >= len(input_data):
                    break
                end = (i + 1) * Sector.SIZE
                sector = Sector(input_data[start:end])
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

    def extend(self, other: XaDatabase):
        num_sectors = 0
        max_data = b''
        for region in self.regions:
            if region.end >= num_sectors:
                num_sectors = region.end + 1
                max_data = region.data[:num_sectors * Sector.SIZE]
        for region in other.regions:
            num_bytes = (region.end + 1) * Sector.SIZE
            self.regions.append(XaRegion(region.channel, region.start + num_sectors, region.end + num_sectors,
                                         max_data + region.data[:num_bytes]))
        self.clean_regions()

    def get_raw(self) -> bytes:
        if len(self.regions) == 0:
            return b''

        raw_data = bytearray(sorted(self.regions, key=lambda r: r.end, reverse=True)[0].data)
        channels = {0: [], 1: [], 2: [], 3: [], 4: [], 5: [], 6: [], 7: []}
        for region in sorted(self.regions, key=lambda r: (r.start, r.channel), reverse=True):
            channels[region.channel].append(region)
        channel_id = 0
        channel_counters = [0, 0, 0, 0, 0, 0, 0, 0]
        while any(channel for channel in channels.values()):
            if channel_regions := channels[channel_id]:
                current_region = channel_regions[-1]
                counter = channel_counters[channel_id]
                raw_start_sector = current_region.start + (counter * 8) + current_region.first_audio_sector
                if raw_start_sector > current_region.end:
                    channel_regions.pop()
                    if not channel_regions:
                        channel_id = (channel_id + 1) % 8
                        continue
                    current_region = channel_regions[-1]
                    counter = 0
                    raw_start_sector = current_region.start + current_region.first_audio_sector
                raw_start = raw_start_sector * Sector.SIZE
                region_start = (counter * 8 + current_region.first_audio_sector) * Sector.SIZE
                raw_data[raw_start:raw_start + Sector.SIZE] = current_region.data[region_start:region_start
                                                                                  + Sector.SIZE]
                channel_counters[channel_id] = counter + 1
            channel_id = (channel_id + 1) % 8

        return bytes(raw_data)

    def append_raw(self, item: bytes):
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
                new_path = (path / f'{i:003}.XA')
                new_path.write_bytes(region.data)
                if fmt == 'wav':
                    audio = XaAudio(new_path)
                    audio.convert(new_path.with_suffix('.wav'))
                    new_path.unlink()
        else:
            raise ValueError('Attempted to export an XA database with no data set')
        return path


def unpack(db_path: str, xa_path: str, out_path: str, convert: bool):
    with open(db_path, 'rb') as f:
        db = XaDatabase.read(f)
    with open(xa_path, 'rb') as f:
        db.set_data(f.read())
    db.export(Path(out_path), 'wav' if convert else None)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Export Galerians XA audio')
    parser.add_argument('-c', '--convert', help='Convert the audio to wav when exporting. If not given, the audio '
                                                'will be exported in the original XA format.')
    parser.add_argument('db', help='Path to the XA database')
    parser.add_argument('xa', help='Path to the XA audio data')
    parser.add_argument('target', help='Path to the directory where audio files will be exported')

    args = parser.parse_args()
    unpack(args.db, args.xa, args.target, args.convert)
