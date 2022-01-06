from __future__ import annotations
from abc import ABC, abstractmethod
from enum import IntEnum
from typing import ByteString, Literal, Optional

from psx.cd.disc import Disc, Sector


class CdRegion(ABC):
    """A contiguous region of related sectors on the disc"""

    sectors: list[Sector]
    sub_regions: list[CdRegion]

    def __init__(self, start: int, end: int = None, name: str = None, byte_len: int = None):
        self.start = start
        self.end = end if end is not None else start
        self.sectors = []
        self.sub_regions = []
        self.data_ptr = 0
        self.name = name
        self.byte_len = byte_len

    def shrink_front(self, num_sectors: int, shift_data: bool = False) -> list[Sector]:
        """
        Remove a number of sectors from the beginning of this region

        :param num_sectors: Number of sectors to remove
        :param shift_data: If True, the data in this region will be copied forward to start at the new first sector.
            Data in the last num_sectors sectors will be lost.
        :return: The sectors that were removed
        """
        if num_sectors > len(self.sectors):
            raise ValueError(f'Tried to shrink by {num_sectors} sectors but only {len(self.sectors)} available')
        if shift_data:
            for i in range(len(self.sectors) - 1, num_sectors + 1, -1):
                self.sectors[i].copy(self.sectors[i - num_sectors])
        result = self.sectors[:num_sectors]
        del self.sectors[:num_sectors]
        self.start += num_sectors
        return result

    def shrink_back(self, num_sectors: int) -> list[Sector]:
        """
        Remove a number of sectors from the end of this region

        :param num_sectors: Number of sectors to remove
        :return: The sectors that were removed
        """

        if num_sectors > len(self.sectors):
            raise ValueError(f'Tried to shrink by {num_sectors} sectors but only {len(self.sectors)} available')
        index = len(self.sectors) - num_sectors
        result = self.sectors[index:]
        del self.sectors[index:]
        self.end -= num_sectors
        return result

    def grow_front(self, sectors: list[Sector], shift_data: bool = True):
        """
        Add sectors to the beginning of this region

        :param sectors: The sectors to add
        :param shift_data: If True, the data in this region will be copied back to start at the new first sector
        """
        self.sectors = sectors + self.sectors
        self.start -= len(sectors)
        if shift_data:
            num_new_sectors = len(sectors)
            for i in range(num_new_sectors, len(self.sectors)):
                self.sectors[i - num_new_sectors].copy(self.sectors[i])

    def grow_back(self, sectors: list[Sector]):
        """
        Add sectors to the end of this region

        :param sectors: The sectors to add
        """
        self.sectors.extend(sectors)
        self.end += len(sectors)

    def patch_sectors(self, sectors: list[Sector]):
        """
        Replace the sectors in this region with the provided list of sectors

        This is ideal for patching files with important data in the sector headers (such as XA audio and STR videos).

        :param sectors: The list of sectors to replace this region with. The number of sectors must be not be greater
            than the number of sectors in this region. If fewer sectors are provided, the remaining sectors at the end
            of the region are left unchanged.
        """
        if len(sectors) > len(self.sectors):
            raise ValueError('Region is not large enough to patch')
        for old_sector, new_sector in zip(self.sectors, sectors):
            old_sector.copy(new_sector)

    def patch_data(self, data: ByteString):
        """
        Replace the data (but not sector headers) in this region's sectors with the provided data

        This is ideal for patching regular files where the sector header information is not part of the file itself.
        Mode 2 form 2 sectors are not supported by this method; any such sectors will be converted to mode 2 form 1
        prior to patching.

        :param data: The data to place in this region. The number of bytes must not be greater than the number of bytes
            that can fit in the data fields of this region's sectors after converting all mode 2 form 2 sectors to mode
            2 form 1.
        """
        # mode 2 form 2 is not supported when patching data, only when patching raw sectors, so ensure that we don't
        # have any such sectors
        for sector in self.sectors:
            if sector.form == 2:
                sector.form = 1
        data_len = len(data)
        if self.data_capacity < data_len:
            raise ValueError('Region is not large enough to patch')
        i = 0
        for sector in self.sectors:
            data_size = sector.data_size
            chunk_size = min(data_size, data_len - i)
            # FIXME: re-calculate EDC and ECC
            sector.data[:chunk_size] = data[i:i+chunk_size]
            i += data_size
            if i >= len(data):
                break

    def update_paths(self, region: CdRegion):
        """
        Update any filesystem data contained in this region that references the provided region

        This is typically used in conjunction with patch_sectors and/or patch_data to notify the filesystem that a file
        has changed size and/or location. Volume descriptors, path tables, and directory records will be updated with
        the new metadata of the file.

        :param region: The region which was changed
        """
        # default implementation has nothing to do, so just pass the message along to subregions
        for r in self.sub_regions:
            r.update_paths(region)

    @property
    def size(self) -> int:
        """The size of this region in sectors"""
        return self.end - self.start + 1

    @property
    def data_capacity(self) -> int:
        return sum(sector.data_size for sector in self.sectors)

    @property
    def data_size(self) -> int:
        """
        The number of bytes of data in this region

        If this region is part of a filesystem structure such as a directory or file with a defined size in bytes, this
        will be the size recorded in the filesystem. Otherwise, it will be the sum of the sizes of the data fields of
        the sectors comprising this region.
        """
        return self.byte_len if self.byte_len is not None else self.data_capacity

    @abstractmethod
    def read(self, disc: Disc) -> list[CdRegion]:
        """
        Read this region and any subregions from the provided disc image

        Subregions are regions that are discoverable from this region. For instance, the system area is always followed
        by the first volume descriptor, then the volume descriptor contains the locations of the path tables and root
        directory, then the root directory contains further directories and files, etc.

        :param disc: The disc image to read from
        :return: The list of regions read, including this one, not necessarily in the order they appear on disc
        """

    def _read_chunk(self, size: int, disc: Disc) -> bytes:
        data = self.sectors[-1].data
        chunk = bytes(data[self.data_ptr:self.data_ptr + size])
        if len(chunk) < size:
            bytes_remaining = size - len(chunk)
            self.sectors.append(disc.read_sector())
            self.end += 1
            data = self.sectors[-1].data
            chunk += bytes(data[:bytes_remaining])
            self.data_ptr = bytes_remaining
        else:
            self.data_ptr += size
        return chunk

    def _write_chunk(self, sector_index: int, data_index: int, data: bytes):
        sector = self.sectors[sector_index]
        sector_data = sector.data
        if len(sector_data) <= data_index:
            # field to patch is entirely in the next sector
            new_start = data_index - len(sector_data)
            sector = self.sectors[sector_index + 1]
            sector_data = sector.data
            sector_data[new_start:new_start + len(data)] = data
        elif data_index < len(sector_data) < data_index + len(data):
            # field to patch crosses sector boundary
            bytes_here = len(sector_data) - data_index
            bytes_there = len(data) - bytes_here
            sector_data[data_index:data_index + bytes_here] = data[:bytes_here]
            sector = self.sectors[sector_index + 1]
            sector_data = sector.data
            sector_data[:bytes_there] = data[bytes_here:]
        else:
            # field to patch is entirely in this sector
            sector_data[data_index:data_index + len(data)] = data

    def write(self, disc: Disc):
        """Write this region to the provided disc image"""
        for sector in self.sectors:
            disc.write_sector(sector)


class SystemArea(CdRegion):
    """The system area occupying sectors 0-15 of the disc"""
    vd: Optional[VolumeDescriptor]

    def __init__(self):
        super().__init__(0, 15)
        self.vd = None

    def read(self, disc: Disc) -> list[CdRegion]:
        regions = [self]
        disc.seek(self.start)
        self.sectors = disc.read_sectors(self.size)
        self.vd = VolumeDescriptor(16)
        regions.extend(self.vd.read(disc))
        self.sub_regions = [self.vd]
        return regions

    def get_primary_volume(self) -> Optional[VolumeDescriptor]:
        volume = self.vd
        while volume:
            if volume.type == VolumeDescriptor.Type.PRIMARY:
                return volume
            volume = volume.next_volume
        return None


class Free(CdRegion):
    """
    A free region of sectors not in use by any file or filesystem structure

    Free regions are identified as regions not used by the CD filesystem. CD images that have data recorded at
    pre-determined locations on the disc which are not recorded in the filesystem may have such data incorrectly
    identified as free.
    """

    def __init__(self, start: int, end: int = None, *, sectors: list[Sector] = None):
        super().__init__(start, end)
        if sectors is not None:
            self.sectors = sectors
            self.end = self.start + len(sectors) - 1

    def read(self, disc: Disc) -> list[CdRegion]:
        disc.seek(self.start)
        self.sectors = disc.read_sectors(self.size)
        return [self]


class PathTable(CdRegion):
    """Table of the directory hierarchy of a volume"""

    name_map: dict[str, tuple[int, int]]

    def __init__(self, start: int, endianness: Literal['little', 'big']):
        super().__init__(start)
        self.endianness = endianness
        self.name_map = {}

    def read(self, disc: Disc) -> list[CdRegion]:
        disc.seek(self.start)
        sector = disc.read_sector()
        self.sectors = [sector]
        self.data_ptr = 0
        qualified_names = []
        while True:
            sector_index = self.end - self.start
            record_pos = self.data_ptr
            name_len = self.sectors[-1].data[self.data_ptr]
            if name_len == 0:
                break
            record_len = 8 + name_len + (name_len & 1)
            record = self._read_chunk(record_len, disc)
            parent_index = int.from_bytes(record[6:8], self.endianness)
            name = record[8:8 + name_len]
            if name == b'\0':
                str_name = '\\'
            else:
                str_name = qualified_names[parent_index - 1]
                if str_name[-1] != '\\':
                    str_name += '\\'
                str_name += name.decode('646')
            qualified_names.append(str_name)
            self.name_map[str_name] = (sector_index, record_pos)

        return [self]

    def update_paths(self, region: CdRegion):
        pieces = region.name.split(':', 1)
        if len(pieces) > 1:
            volume_path = pieces[1]
            if volume_path in self.name_map:
                sector_index, record_pos = self.name_map[volume_path]
                new_loc = region.start.to_bytes(2, self.endianness)
                self._write_chunk(sector_index, record_pos + 6, new_loc)


class VolumeDescriptor(CdRegion):
    """Descriptor of a volume on the disc"""

    class Type(IntEnum):
        BOOT = 0
        PRIMARY = 1
        SUPPLEMENTARY = 2
        PARTITION = 3
        TERMINATOR = 255

    type: Optional[Type]
    path_tables: list[PathTable]

    def __init__(self, start: int, end: int = None, name: str = None):
        super().__init__(start, end, name)
        self.type = None
        self.space_size = 0
        self.path_tables = []

    def read(self, disc: Disc) -> list[CdRegion]:
        regions = [self]
        disc.seek(self.start)
        sector = disc.read_sector()
        self.sectors = [sector]
        self.path_tables = []
        data = sector.data
        self.type = VolumeDescriptor.Type(data[0])
        if data[1:6] != b'CD001':
            raise ValueError(f'Invalid standard identifier in volume descriptor at sector {self.start}')
        if data[6] != 1:
            raise ValueError(f'Unknown volume descriptor version {data[6]}')
        if self.type == VolumeDescriptor.Type.BOOT:
            self.name = data[39:71].tobytes().decode('646').strip()
        elif self.type != VolumeDescriptor.Type.TERMINATOR:
            self.name = data[40:72].tobytes().decode('646').strip()
            if self.type != VolumeDescriptor.Type.PARTITION:
                # primary or supplementary partition
                self.space_size = int.from_bytes(data[80:84], 'little')
                l_path_table_loc = int.from_bytes(data[140:144], 'little')
                l_path_table = PathTable(l_path_table_loc, 'little')
                self.path_tables.append(l_path_table)
                regions.extend(l_path_table.read(disc))
                opt_l_path_table_loc = int.from_bytes(data[144:148], 'little')
                if opt_l_path_table_loc > 0:
                    opt_l_path_table = PathTable(opt_l_path_table_loc, 'little')
                    self.path_tables.append(opt_l_path_table)
                    regions.extend(opt_l_path_table.read(disc))

                m_path_table_loc = int.from_bytes(data[148:152], 'big')
                m_path_table = PathTable(m_path_table_loc, 'big')
                self.path_tables.append(m_path_table)
                regions.extend(m_path_table.read(disc))
                opt_m_path_table_loc = int.from_bytes(data[152:156], 'big')
                if opt_m_path_table_loc > 0:
                    opt_m_path_table = PathTable(opt_m_path_table_loc, 'big')
                    self.path_tables.append(opt_m_path_table)
                    regions.extend(opt_m_path_table.read(disc))

                extent_loc = int.from_bytes(data[158:162], 'little')
                data_len = int.from_bytes(data[166:170], 'little')
                root_dir = Directory(extent_loc, name=f'{self.name}:\\', byte_len=data_len)
                regions.extend(root_dir.read(disc))

        if self.type != VolumeDescriptor.Type.TERMINATOR:
            next_vd = VolumeDescriptor(self.start+1)
            regions.extend(next_vd.read(disc))

        self.sub_regions = regions[1:]
        return regions

    @property
    def next_volume(self) -> Optional[VolumeDescriptor]:
        """The next volume descriptor after this one, or None if this is the final volume descriptor"""
        return self.sub_regions[-1] if self.type != VolumeDescriptor.Type.TERMINATOR else None

    @property
    def is_filesystem(self) -> bool:
        """Whether this descriptor describes a volume containing a filesystem"""
        return self.type in [VolumeDescriptor.Type.PRIMARY, VolumeDescriptor.Type.SUPPLEMENTARY]

    def update_paths(self, region: CdRegion):
        if self.is_filesystem and region.name.startswith(f'{self.name}:\\'):
            data = self.sectors[0].data
            if isinstance(region, Directory) and region.name == f'{self.name}:\\':
                # this is the root directory of our volume; update directory record
                data[158:162] = region.start.to_bytes(4, 'little')
                data[162:166] = region.start.to_bytes(4, 'big')
                data[166:170] = region.data_size.to_bytes(4, 'little')
                data[170:174] = region.data_size.to_bytes(4, 'big')

            if region.end - self.start >= self.space_size:
                # this region is within our volume and now extends past the end; expand our volume
                self.space_size = region.end - self.start
                data[80:84] = self.space_size.to_bytes(4, 'little')
                data[84:88] = self.space_size.to_bytes(4, 'big')
            if isinstance(region, Directory):
                # this region is a directory within our volume; update path tables
                for path_table in self.path_tables:
                    path_table.update_paths(region)
        elif self.type != VolumeDescriptor.Type.TERMINATOR:
            # this doesn't affect us; pass the message along to the next volume if there is one
            # next volume is always the last subregion
            self.sub_regions[-1].update_paths(region)


class Directory(CdRegion):
    """The region of sectors comprising a directory in the CD filesystem"""

    class Flags(IntEnum):
        HIDDEN = 0x01
        DIRECTORY = 0x02
        ASSOCIATED = 0x04
        RECORD = 0x08
        PROTECTION = 0x10
        MULTI_EXTENT = 0x80

    name_map: dict[str, tuple[int, int, Optional[CdRegion]]]

    def __init__(self, start: int, end: int = None, name: str = None, byte_len: int = None):
        super().__init__(start, end, name, byte_len)
        self.name_map = {}

    def read(self, disc: Disc) -> list[CdRegion]:
        regions = [self]
        disc.seek(self.start)
        sector = disc.read_sector()
        self.sectors = [sector]
        self.data_ptr = 0
        while True:
            sector_index = self.end - self.start
            record_pos = self.data_ptr
            record_len = self.sectors[-1].data[self.data_ptr]
            if record_len == 0:
                break
            record = self._read_chunk(record_len, disc)
            xa_len = record[1]
            if xa_len > 0:
                raise NotImplementedError(f'Extended attribute records not supported in directory {self.name}')
            name_len = record[32]
            name = record[33:33+name_len]
            if name == b'\0':
                str_name = '.'
                new_region = self
            elif name == b'\x01':
                str_name = '..'
                new_region = None
            else:
                extent_loc = int.from_bytes(record[2:6], 'little')
                data_len = int.from_bytes(record[10:14], 'little')
                flags = record[25]
                interleave_gap = record[27]
                if interleave_gap > 0:
                    raise NotImplementedError(f'Interleave not supported in directory {self.name}')
                str_name = name.decode('646')
                full_name = self.name
                if full_name[-1] != '\\':
                    full_name += '\\'
                full_name += str_name
                if flags & Directory.Flags.DIRECTORY:
                    new_region = Directory(extent_loc, name=full_name, byte_len=data_len)
                else:
                    new_region = File(extent_loc, name=full_name, byte_len=data_len)
                regions.extend(new_region.read(disc))
            self.name_map[str_name] = (sector_index, record_pos, new_region)

        self.sub_regions = regions[1:]
        return regions

    def update_record(self, name: str, region: CdRegion = None):
        sector_index, record_pos, stored_region = self.name_map[name]
        if region is None:
            region = stored_region
        bin_start = region.start.to_bytes(4, 'little') + region.start.to_bytes(4, 'big')
        bin_len = region.data_size.to_bytes(4, 'little') + region.data_size.to_bytes(4, 'big')
        self._write_chunk(sector_index, record_pos + 2, bin_start + bin_len)

    def update_paths(self, region: CdRegion):
        if region.name == self.name:
            self.update_record('.')
            # if we're the root directory
            if self.name[-2:] == ':\\':
                self.update_record('..', self)
            # update any sub-directories
            for path in self.name_map:
                sub_region = self.name_map[path][2]
                if path not in ['.', '..'] and isinstance(sub_region, Directory):
                    sub_region.update_record('..', self)
        else:
            pieces = region.name.rsplit('\\', 1)
            if len(pieces) > 1:
                parent_dir = pieces[0]
                if parent_dir[-1] == ':':
                    parent_dir += '\\'
                if parent_dir == self.name:
                    self.update_record(pieces[1])


class File(CdRegion):
    """The region of sectors comprising a file in the CD filesystem"""

    def read(self, disc: Disc) -> list[CdRegion]:
        self.sectors = []
        len_so_far = 0
        disc.seek(self.start)
        self.end = self.start
        while len_so_far < self.byte_len:
            sector = disc.read_sector()
            len_so_far += len(sector.data)
            self.sectors.append(sector)
            self.end += 1
        self.end -= 1
        return [self]

    def patch_sectors(self, sectors: list[Sector]):
        super().patch_sectors(sectors)
        self.byte_len = None

    def patch_data(self, data: ByteString):
        super().patch_data(data)
        self.byte_len = len(data)
