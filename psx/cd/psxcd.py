import re

from dataclasses import dataclass
from math import ceil
from typing import BinaryIO, ByteString

from psx.cd.region import CdRegion, SystemArea, Free
from psx.cd.disc import Disc, Sector


PRIMARY_ALIAS = re.compile(r'^(cdrom:)?\\', re.IGNORECASE)
DEFAULT_SECTOR_SIZE = 0x800


@dataclass
class Patch:
    path: str
    raw: bool
    data: ByteString


class PsxCd:
    def __init__(self, source: BinaryIO):
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
            new_region.read(disc)
            self.regions.append(new_region)

        primary_volume = self.system_area.get_primary_volume()
        if not primary_volume:
            raise LookupError('CD has no primary volume')
        self.primary_volume_name = primary_volume.name
        self.name_map = {r.name.lower(): i for i, r in enumerate(self.regions) if r.name}

    def remove_region(self, index: int):
        region = self.regions[index]
        if region.name:
            del self.name_map[region.name.lower()]
        del self.regions[index]
        for name in self.name_map:
            if self.name_map[name] > index:
                self.name_map[name] -= 1

    def add_region(self, index: int, new_region: CdRegion):
        self.regions.insert(index, new_region)
        for name in self.name_map:
            if self.name_map[name] >= index:
                self.name_map[name] += 1
        if new_region.name:
            self.name_map[new_region.name.lower()] = index

    def fit_region(self, index: int, new_size: int) -> set[CdRegion]:
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
                    self.remove_region(index + 1)
                else:
                    free_sectors = free.shrink_front(sectors_needed)
                f.grow_back(free_sectors)
                sectors_needed -= len(free_sectors)
            if sectors_needed > 0 and index > 0 and isinstance(self.regions[index - 1], Free):
                free = self.regions[index - 1]
                sectors_available = len(free.sectors)
                if sectors_available <= sectors_needed:
                    free_sectors = free.shrink_back(sectors_available)
                    self.remove_region(index - 1)
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
                            self.remove_region(i)
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
                            self.remove_region(i)
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
                self.add_region(index + 1, Free(f.end + 1, sectors=free_sectors))

        return regions_changed

    def patch_raw(self, index: int, sectors: list[Sector]) -> set[CdRegion]:
        f = self.regions[index]
        old_pos = (f.start, f.end)
        old_size = f.data_size
        regions_changed = self.fit_region(index, len(sectors))
        f.patch_sectors(sectors)
        if old_pos != (f.start, f.end) or old_size != f.data_size:
            regions_changed.add(f)
        return regions_changed

    def patch_data(self, index: int, data: ByteString) -> set[CdRegion]:
        f = self.regions[index]
        old_pos = (f.start, f.end)
        old_size = f.data_size
        # mode 2 form 2 isn't supported when patching data, so we assume a fixed data size of 0x800 bytes per sector
        sectors_needed = ceil(len(data) / DEFAULT_SECTOR_SIZE)
        regions_changed = self.fit_region(index, sectors_needed)
        f.patch_data(data)
        if old_pos != (f.start, f.end) or old_size != f.data_size:
            regions_changed.add(f)
        return regions_changed

    def patch(self, patches: list[Patch]):
        for patch in patches:
            patch.path = PRIMARY_ALIAS.sub(f'{self.primary_volume_name}:\\\\', patch.path)

        # sort patches for files that are getting smaller before patches for files that are getting larger so we have
        # the maximum amount of free space available before trying to expand things
        patches.sort(key=self.patch_sort)
        regions_changed = set()
        for patch in patches:
            path = patch.path.lower()
            index = self.name_map[path]
            if patch.raw:
                if len(patch.data) % Sector.SIZE != 0:
                    raise ValueError(f'Raw patch {patch.path} does not contain a whole number of sectors')
                sectors = [Sector(patch.data[i:i+Sector.SIZE]) for i in range(0, len(patch.data), Sector.SIZE)]
                regions_changed.update(self.patch_raw(index, sectors))
            else:
                regions_changed.update(self.patch_data(index, patch.data))

        # update filesystem with new locations and sizes for things that were moved
        for region in regions_changed:
            self.system_area.update_paths(region)

    def write(self, destination: BinaryIO):
        out_disc = Disc(destination)
        for region in self.regions:
            region.write(out_disc)

    def patch_sort(self, patch: Patch):
        path = patch.path.lower()
        index = self.name_map[path]
        if patch.raw:
            new_num_sectors = len(patch.data) // Sector.SIZE
        else:
            new_num_sectors = ceil(len(patch.data) / DEFAULT_SECTOR_SIZE)
        region = self.regions[index]
        return new_num_sectors - region.size
