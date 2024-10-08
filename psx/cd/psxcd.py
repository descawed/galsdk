import os
import re

from dataclasses import dataclass
from math import ceil
from pathlib import Path
from typing import BinaryIO, ByteString, Iterator

from psx.cd.region import CdRegion, SystemArea, Directory, Free
from psx.cd.disc import Disc, Sector


PRIMARY_ALIAS = re.compile(r'^(cdrom:)?\\', re.IGNORECASE)
DEFAULT_SECTOR_SIZE = 0x800


@dataclass
class Patch:
    """New or updated data to be patched into a file on the CD."""

    path: str
    data: ByteString
    is_data_raw_sectors: bool = False


@dataclass
class DirectoryEntry:
    """Information about a file or directory within a directory"""

    name: str
    path: str
    is_directory: bool


class PsxCd:
    """
    A PSX CD image

    This class enables extracting files from PSX CD images and patching files in such images. It does not support the
    full range of CD-ROM XA functionality, only a subset sufficient to work with Galerians, so it may or may not be able
    to successfully work with other PSX games.
    """

    def __init__(self, source: BinaryIO, *, ignore_invalid: bool = False):
        """
        Load a PSX CD image for patching or extracting

        No reference to the source is retained; the entire image is loaded into memory.

        :param source: A byte stream from which to read the CD image
        :param ignore_invalid: Whether to ignore invalid sectors at the end of the file
        """
        disc = Disc(source)
        self.system_area = SystemArea()
        self.regions = self.system_area.read(disc)
        self.regions.sort(key=lambda r: (r.start, r.end))
        # while loop instead of for because len(self.regions) is changing in this loop
        i = 0
        while i+1 < len(self.regions):
            first_region = self.regions[i]
            next_region = self.regions[i+1]
            if next_region.start - first_region.end > 1:
                new_region = Free(first_region.end+1, next_region.start-1)
                new_region.read(disc)
                self.regions.insert(i+1, new_region)
            i += 1

        num_sectors = disc.num_sectors
        if num_sectors - self.regions[-1].end > 1:
            new_region = Free(self.regions[-1].end+1, num_sectors-1)
            new_region.read(disc, stop_at_invalid=ignore_invalid)
            self.regions.append(new_region)

        self.primary_volume = self.system_area.get_primary_volume()
        if not self.primary_volume:
            raise LookupError('CD has no primary volume')
        self.name_map = {r.name.lower(): i for i, r in enumerate(self.regions) if r.name}

    def __getitem__(self, path: str | None) -> CdRegion:
        cleaned_path = self._clean_path(path)
        index = self.name_map.get(cleaned_path)
        if index is None:
            raise FileNotFoundError(f'{path} does not exist')
        return self.regions[index]

    def _remove_region(self, index: int):
        region = self.regions[index]
        if region.name:
            del self.name_map[region.name.lower()]
        del self.regions[index]
        for name in self.name_map:
            if self.name_map[name] > index:
                self.name_map[name] -= 1

    def _add_region(self, index: int, new_region: CdRegion):
        self.regions.insert(index, new_region)
        for name in self.name_map:
            if self.name_map[name] >= index:
                self.name_map[name] += 1
        if new_region.name:
            self.name_map[new_region.name.lower()] = index

    def _fit_region(self, index: int, new_size: int) -> set[CdRegion]:
        f = self.regions[index]
        current_size = len(f.sectors)
        regions_changed = set()
        if current_size < new_size:
            sectors_needed = new_size - current_size
            if index + 1 < len(self.regions) and isinstance(self.regions[index + 1], Free):
                free = self.regions[index + 1]
                sectors_available = len(free.sectors)
                if sectors_available <= sectors_needed:
                    free_sectors = free.shrink_front(sectors_available)
                    self._remove_region(index + 1)
                else:
                    free_sectors = free.shrink_front(sectors_needed)
                f.grow_back(free_sectors)
                sectors_needed -= len(free_sectors)
            if sectors_needed > 0 and index > 0 and isinstance(self.regions[index - 1], Free):
                free = self.regions[index - 1]
                sectors_available = len(free.sectors)
                if sectors_available <= sectors_needed:
                    free_sectors = free.shrink_back(sectors_available)
                    self._remove_region(index - 1)
                    index -= 1
                else:
                    free_sectors = free.shrink_back(sectors_needed)
                f.grow_front(free_sectors)
                sectors_needed -= len(free_sectors)
            if sectors_needed > 0:
                # search forward looking for free space until we have enough. move all subsequent regions forward
                # to consolidate free space adjacent to the file and then expand it into that space. update entries in
                # directory records, path tables, and volume descriptors as necessary.
                i = index + 1
                while i < len(self.regions):
                    candidate = self.regions[i]
                    if isinstance(candidate, Free):
                        update_index = i - 1
                        sectors_available = len(candidate.sectors)
                        if sectors_available <= sectors_needed:
                            free_sectors = candidate.shrink_front(sectors_available)
                            self._remove_region(i)
                        else:
                            free_sectors = candidate.shrink_front(sectors_needed)
                            i += 1
                        num_sectors = len(free_sectors)
                        # shift each intervening region down by the number of available sectors
                        for update_index in range(update_index, index, -1):
                            previous_region = self.regions[update_index]
                            previous_region.grow_back(free_sectors)
                            free_sectors = previous_region.shrink_front(num_sectors, True)
                            regions_changed.add(previous_region)
                        # add the remaining new sectors to the file
                        f.grow_back(free_sectors)
                        sectors_needed -= num_sectors
                        if sectors_needed <= 0:
                            break
                    else:
                        i += 1
            if sectors_needed > 0:
                # search backward looking for free space until we have enough. move all subsequent regions backward
                # to consolidate free space adjacent to the file and then expand it into that space. update entries in
                # directory records, path tables, and volume descriptors as necessary.
                i = index - 1
                while i >= 0:
                    candidate = self.regions[i]
                    if isinstance(candidate, Free):
                        update_index = i + 1
                        sectors_available = len(candidate.sectors)
                        if sectors_available <= sectors_needed:
                            free_sectors = candidate.shrink_back(sectors_available)
                            self._remove_region(i)
                        else:
                            free_sectors = candidate.shrink_back(sectors_needed)
                            i -= 1
                        num_sectors = len(free_sectors)
                        # shift each intervening region up by the number of available sectors
                        for update_index in range(update_index, index):
                            previous_region = self.regions[update_index]
                            previous_region.grow_front(free_sectors)
                            free_sectors = previous_region.shrink_back(num_sectors)
                            regions_changed.add(previous_region)
                        # add the remaining new sectors to the file
                        f.grow_front(free_sectors)
                        sectors_needed -= num_sectors
                        if sectors_needed <= 0:
                            break
                    else:
                        i -= 1
            if sectors_needed > 0:
                raise EOFError('Not enough space on the disc to resize')
        elif current_size > new_size:
            free_sectors = f.shrink_back(current_size - new_size)
            if index + 1 < len(self.regions) and isinstance(self.regions[index + 1], Free):
                self.regions[index + 1].grow_front(free_sectors, False)
            else:
                self._add_region(index + 1, Free(f.end + 1, sectors=free_sectors))

        return regions_changed

    def _patch_raw(self, index: int, sectors: list[Sector]) -> set[CdRegion]:
        f = self.regions[index]
        old_pos = (f.start, f.end)
        old_size = f.data_size
        regions_changed = self._fit_region(index, len(sectors))
        f.patch_sectors(sectors)
        if old_pos != (f.start, f.end) or old_size != f.data_size:
            regions_changed.add(f)
        return regions_changed

    def _patch_data(self, index: int, data: ByteString) -> set[CdRegion]:
        f = self.regions[index]
        old_pos = (f.start, f.end)
        old_size = f.data_size
        # mode 2 form 2 isn't supported when patching data, so we assume a fixed data size of 0x800 bytes per sector
        sectors_needed = ceil(len(data) / DEFAULT_SECTOR_SIZE)
        regions_changed = self._fit_region(index, sectors_needed)
        f.patch_data(data)
        if old_pos != (f.start, f.end) or old_size != f.data_size:
            regions_changed.add(f)
        return regions_changed

    def patch(self, patches: list[Patch]):
        """
        Apply one or more patches to files on the CD

        The contents of the CD image will be rearranged if necessary to make room for any files that have grown. This
        method cannot be used to add or remove files, only change existing files.

        :param patches: The set of patches to apply
        """
        for patch in patches:
            patch.path = self._clean_path(patch.path)

        # sort patches for files that are getting smaller before patches for files that are getting larger so we have
        # the maximum amount of free space available before trying to expand things
        patches.sort(key=self._patch_sort)
        regions_changed = set()
        for patch in patches:
            index = self.name_map[patch.path]
            if patch.is_data_raw_sectors:
                if len(patch.data) % Sector.SIZE != 0:
                    raise ValueError(f'Raw patch {patch.path} does not contain a whole number of sectors')
                sectors = [Sector(patch.data[i:i+Sector.SIZE]) for i in range(0, len(patch.data), Sector.SIZE)]
                regions_changed.update(self._patch_raw(index, sectors))
            else:
                regions_changed.update(self._patch_data(index, patch.data))

        # update filesystem with new locations and sizes for things that were moved
        for region in regions_changed:
            self.system_area.update_paths(region)

    def _clean_path(self, path: str | None) -> str:
        if path is None:
            path = f'{self.primary_volume.name}:\\'
        path = PRIMARY_ALIAS.sub(f'{self.primary_volume.name}:\\\\', path)
        if path[-1] == '\\' and path[-2] != ':':
            # remove any trailing slash unless it's the root directory
            path = path[:-1]
        return path.lower()

    def is_dir(self, path: str) -> bool:
        try:
            return isinstance(self[path], Directory)
        except FileNotFoundError:
            return False

    def list_dir(self, path: str = None) -> Iterator[DirectoryEntry]:
        """
        List the contents of a directory on the primary volume of the CD

        :param path: The path to the directory whose contents to list. If None, the root directory.
        :return: A list of directory entries
        """
        directory = self[path]
        if not isinstance(directory, Directory):
            raise NotADirectoryError(f'{path} is not a directory')
        for entry in directory.contents:
            yield DirectoryEntry(entry.name.rsplit('\\', 1)[1], entry.name, isinstance(entry, Directory))

    def extract(self, path: str, destination: BinaryIO, raw: bool = False, extend: bool = False):
        """
        Extract a file at the given path to the provided destination byte stream

        :param path: Path to the file to extract
        :param destination: File-like object to write the extracted file to
        :param raw: If True, the full raw sectors of the file will be extracted, including sector header and error
            correction codes
        :param extend: If True, include any sectors marked free after the end of the file.
        """
        cleaned_path = self._clean_path(path)
        index = self.name_map.get(cleaned_path)
        if index is None:
            raise FileNotFoundError(f'{path} does not exist')
        region = self.regions[index]
        next_region = None
        if extend and index + 1 < len(self.regions) and isinstance(self.regions[index + 1], Free):
            next_region = self.regions[index + 1]
        if raw:
            disc = Disc(destination)
            region.write(disc)
            if next_region is not None:
                next_region.write(disc)
        else:
            region.write_data(destination)
            if next_region is not None:
                next_region.write_data(destination)

    def write(self, destination: BinaryIO):
        """
        Write the contents of the CD, with any patches applied, to the given stream

        :param destination: File-like object to write the CD image to
        """
        out_disc = Disc(destination)
        for region in self.regions:
            region.write(out_disc)

    def _patch_sort(self, patch: Patch):
        path = patch.path.lower()
        index = self.name_map[path]
        if patch.is_data_raw_sectors:
            new_num_sectors = len(patch.data) // Sector.SIZE
        else:
            new_num_sectors = ceil(len(patch.data) / DEFAULT_SECTOR_SIZE)
        region = self.regions[index]
        return new_num_sectors - region.size


def patch_cd(image_path: Path, cd_path: str, input_path: Path, raw: bool, ignore_invalid: bool):
    with image_path.open('rb') as f:
        cd = PsxCd(f, ignore_invalid=ignore_invalid)
    with input_path.open('rb') as f:
        data = f.read()
    patch = Patch(cd_path, data, raw)
    cd.patch([patch])
    with image_path.open('wb') as f:
        cd.write(f)


def extract_file(cd: PsxCd, output_path: Path, cd_path: str, raw: bool, extend: bool, keep_hierarchy: bool,
                 keep_dates: bool, depth: int = 0):
    base_name = cd_path.rsplit('\\', 1)[-1]
    if cd.is_dir(cd_path):
        set_dir_date = False
        if keep_hierarchy and base_name and depth > 0:
            output_path = output_path / base_name
            output_path.mkdir(exist_ok=True)
            set_dir_date = keep_dates

        for entry in cd.list_dir(cd_path):
            extract_file(cd, output_path, entry.path, raw, extend, keep_hierarchy, keep_dates, depth + 1)

        # need to set the date after extracting the files because that changes the date
        if set_dir_date and (modified_date := cd[cd_path].last_modified):
            timestamp = modified_date.timestamp()
            os.utime(output_path, (timestamp, timestamp))
    else:
        base_name = base_name.split(';', 1)[0]
        new_path = output_path / base_name
        with new_path.open('wb') as f:
            cd.extract(cd_path, f, raw, extend)
        if keep_dates and (modified_date := cd[cd_path].last_modified):
            timestamp = modified_date.timestamp()
            os.utime(new_path, (timestamp, timestamp))


def extract_files(image_path: Path, output_path: Path, cd_paths: list[str], raw: bool, extend: bool,
                  keep_hierarchy: bool, ignore_invalid: bool, keep_dates: bool):
    with image_path.open('rb') as f:
        cd = PsxCd(f, ignore_invalid=ignore_invalid)

    if (len(cd_paths) > 1 or cd.is_dir(cd_paths[0])) and not output_path.is_dir():
        if not output_path.exists():
            output_path.mkdir()
        else:
            raise NotADirectoryError('Output path must be a directory when extracting multiple files')

    if output_path.is_dir():
        for cd_path in cd_paths:
            extract_file(cd, output_path, cd_path, raw, extend, keep_hierarchy, keep_dates)
    else:
        cd_path = cd_paths[0]
        with output_path.open('wb') as f:
            cd.extract(cd_path, f, raw, extend)
        if keep_dates and (modified_date := cd[cd_path].last_modified):
            timestamp = modified_date.timestamp()
            os.utime(output_path, (timestamp, timestamp))


def print_dir(cd: PsxCd, dir_path: str | None, recursive: bool, depth: int = 0):
    indent = '\t' * depth
    for entry in cd.list_dir(dir_path):
        name = entry.name
        if entry.is_directory:
            name += '/'
        print(f'{indent}{name}')
        if entry.is_directory and recursive:
            print_dir(cd, entry.path, recursive, depth + 1)


def dir_cmd(image_path: Path, cd_path: str | None, recursive: bool, ignore_invalid: bool):
    with image_path.open('rb') as f:
        cd = PsxCd(f, ignore_invalid=ignore_invalid)

    print_dir(cd, cd_path, recursive)


def print_layout(image_path: Path, ignore_invalid: bool):
    with image_path.open('rb') as f:
        cd = PsxCd(f, ignore_invalid=ignore_invalid)

    for region in cd.regions:
        print(region)


def validate(image_path: Path, verbose: bool):
    import sys

    success = True

    with Disc(image_path.open('rb')) as disc:
        i = 0
        while sector := disc.read_sector():
            if sector.validate_edc():
                i += 1
                continue

            success = False
            if not verbose:
                break

            print(f'{i} ({sector.minute:02}:{sector.second:02}:{sector.sector:02}): invalid EDC')
            i += 1

    sys.exit(0 if success else 1)


def cli_main():
    import argparse

    parser = argparse.ArgumentParser(description='Patch or extract files in CD images')
    parser.add_argument('-i', '--ignore-invalid', help='Ignore invalid sectors at the end of the image',
                        action='store_true')

    subparsers = parser.add_subparsers()

    patch_parser = subparsers.add_parser('patch', help='Patch a file in the CD image')
    patch_parser.add_argument('-r', '--raw', help='The input file is raw CD sectors', action='store_true')
    patch_parser.add_argument('cd', help='Path to the CD image to be patched', type=Path)
    patch_parser.add_argument('path', help='Path on the CD to be patched')
    patch_parser.add_argument('input', help='Path to the file that will be patched into the CD', type=Path)
    patch_parser.set_defaults(action=lambda a: patch_cd(a.cd, a.path, a.input, a.raw, a.ignore_invalid))

    extract_parser = subparsers.add_parser('extract', help='Extract files from the CD image')
    extract_parser.add_argument('-r', '--raw', help='Extract the file(s) as raw CD sectors', action='store_true')
    extract_parser.add_argument('-x', '--extend', help='Include any sectors marked free after the end of each file',
                                action='store_true')
    extract_parser.add_argument('-k', '--keep-hierarchy', help='When extracting a directory, replicate the'
                                'directory hierarchy within it', action='store_true')
    extract_parser.add_argument('-d', '--keep-dates', help='Keep the modification timestamp on extracted files',
                                action='store_true')
    extract_parser.add_argument('cd', help='Path to the CD image', type=Path)
    extract_parser.add_argument('output', help='Path to extract file(s) to. If more than one file is being '
                                'extracted, this must be a directory.', type=Path)
    extract_parser.add_argument('paths', help='Path(s) on the CD to be extracted', nargs='+')
    extract_parser.set_defaults(action=lambda a: extract_files(a.cd, a.output, a.paths, a.raw, a.extend,
                                                               a.keep_hierarchy, a.ignore_invalid, a.keep_dates))

    dir_parser = subparsers.add_parser('dir', help='List directory structure of the CD image')
    dir_parser.add_argument('-r', '--recursive', help='List directories recursively', action='store_true')
    dir_parser.add_argument('cd', help='Path to the CD image', type=Path)
    dir_parser.add_argument('dir', help='Path to the directory to list. Defaults to root directory.', nargs='?')
    dir_parser.set_defaults(action=lambda a: dir_cmd(a.cd, a.dir, a.recursive, a.ignore_invalid))

    layout_parser = subparsers.add_parser('layout', help='Print the layout of the CD image')
    layout_parser.add_argument('cd', help='Path to the CD image', type=Path)
    layout_parser.set_defaults(action=lambda a: print_layout(a.cd, a.ignore_invalid))

    validate_parser = subparsers.add_parser('validate', help='Validate CD error detection/correction codes')
    validate_parser.add_argument('-v', '--verbose', help='Print sectors that fail to validate', action='store_true')
    validate_parser.add_argument('cd', help='Path to the CD image', type=Path)
    validate_parser.set_defaults(action=lambda a: validate(a.cd, a.verbose))

    args = parser.parse_args()
    args.action(args)
