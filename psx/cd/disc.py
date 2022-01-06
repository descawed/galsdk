from __future__ import annotations
from enum import IntEnum
from typing import BinaryIO, ByteString, Optional


class SubMode(IntEnum):
    END_OF_RECORD = 0x01
    VIDEO = 0x02
    AUDIO = 0x04
    DATA = 0x08
    TRIGGER = 0x10
    FORM2 = 0x20
    REAL_TIME = 0x40
    END_OF_FILE = 0x80


class CodingInfo(IntEnum):
    STEREO = 0x01
    RATE_18900 = 0x04
    BITS_8 = 0x10
    EMPHASIS = 0x40


class Sector:
    """A single sector of a Disc"""
    SIZE = 2352
    SYNC_HEADER = b'\0\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\0'

    def __init__(self, raw: ByteString = None, *, minute: int = 0, second: int = 0, sector: int = 0, mode: int = 0,
                 form: int = None):
        """
        Create a new disc sector

        :param raw: Raw data of the sector, including the CD-ROM XA sector header. If None (the default), a new sector
            will be created with the attributes specified by the keyword arguments. Otherwise, the keyword arguments
            will be ignored.
        :param minute: Minute number of the sector position
        :param second: Second number of the sector position
        :param sector: Sector number of the sector position
        :param mode: Sector mode
        :param form: For mode 2 sectors, form 1 or 2
        """
        if raw is None:
            self._raw = bytearray(Sector.SIZE)
            self._raw[:len(self.SYNC_HEADER)] = self.SYNC_HEADER
            self.minute = minute
            self.second = second
            self.sector = sector
            self.mode = mode
            if mode == 2 and form is not None:
                self.form = form
        else:
            size = len(raw)
            if size != self.SIZE:
                raise ValueError(f'Expected {self.SIZE} bytes in sector, found {size}')
            self._raw = bytearray(raw)
            sync_header = self._raw[:len(self.SYNC_HEADER)]
            if sync_header != self.SYNC_HEADER:
                raise ValueError(f'Bad sector header: expected {self.SYNC_HEADER}, found {sync_header}')

    @property
    def raw(self) -> bytes:
        return bytes(self._raw)

    @property
    def minute(self) -> int:
        return self._raw[0xc]

    @minute.setter
    def minute(self, value: int):
        self._raw[0xc] = value

    @property
    def second(self) -> int:
        return self._raw[0xd]

    @second.setter
    def second(self, value: int):
        self._raw[0xd] = value

    @property
    def sector(self) -> int:
        return self._raw[0xe]

    @sector.setter
    def sector(self, value: int):
        self._raw[0xe] = value

    @property
    def mode(self) -> int:
        return self._raw[0xf]

    @mode.setter
    def mode(self, value: int):
        self._raw[0xf] = value

    @property
    def file_number(self) -> Optional[int]:
        return self._raw[0x10] if self.mode == 2 else None

    @file_number.setter
    def file_number(self, value: int):
        if self.mode != 2:
            raise AttributeError(f'Cannot set file number on a mode {self.mode} sector')
        self._raw[0x10] = self._raw[0x14] = value

    @property
    def channel(self) -> Optional[int]:
        return self._raw[0x11] if self.mode == 2 else None

    @channel.setter
    def channel(self, value: int):
        if self.mode != 2:
            raise AttributeError(f'Cannot set channel on a mode {self.mode} sector')
        self._raw[0x11] = self._raw[0x15] = value

    @property
    def sub_mode(self) -> Optional[int]:
        return self._raw[0x12] if self.mode == 2 else None

    @sub_mode.setter
    def sub_mode(self, value: int):
        if self.mode != 2:
            raise AttributeError(f'Cannot set sub-mode on a mode {self.mode} sector')
        self._raw[0x12] = self._raw[0x16] = value

    @property
    def coding_info(self) -> Optional[int]:
        return self._raw[0x13] if self.mode == 2 else None

    @coding_info.setter
    def coding_info(self, value: int):
        if self.mode != 2:
            raise AttributeError(f'Cannot set coding info on a mode {self.mode} sector')
        self._raw[0x13] = self._raw[0x17] = value

    @property
    def form(self) -> Optional[int]:
        if self.mode == 2:
            return 1 if self.sub_mode & SubMode.FORM2 == 0 else 2
        return None

    @form.setter
    def form(self, form: int):
        if self.mode != 2:
            raise AttributeError(f'Cannot set form on a mode {self.mode} sector')
        if form == 1:
            self.sub_mode &= ~SubMode.FORM2
        elif form == 2:
            self.sub_mode |= SubMode.FORM2
        else:
            raise ValueError(f'Invalid form {form}; expected 1 or 2')

    @property
    def data_size(self) -> int:
        match self.mode:
            case 0:
                return 0
            case 1:
                return 0x800
            case 2:
                return 0x800 if self.form == 1 else 0x914
            case _:
                raise ValueError(f'Invalid mode {self.mode}; expected 0, 1, or 2')

    @property
    def data(self) -> memoryview:
        """A writable view of this sector's data field"""
        view = memoryview(self._raw)
        match self.mode:
            case 0:
                return view[0x10:]
            case 1:
                return view[0x10:0x810]
            case 2:
                return view[0x18:0x818] if self.form == 1 else view[0x18:0x92c]
            case _:
                raise ValueError(f'Invalid mode {self.mode}; expected 0, 1, or 2')

    def copy(self, other: Sector):
        """Copy data and attributes from another sector while leaving location intact"""
        self._raw[0x10:] = other._raw[0x10:]


class Disc:
    """Wrapper around a raw CD-ROM XA disc image"""

    def __init__(self, data: BinaryIO):
        """
        Create a Disc to read sectors from a given disc image

        :param data: A file-like object containing the raw binary data of the disc image
        """
        self.data = data
        self.offset = 0
        self.data.seek(self.offset)

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.data.close()

    def seek(self, offset: int):
        """
        Seek to a given a sector in the disc image

        :param offset: Number of the desired sector from the start of the image, with the first sector having offset 0
        """
        new_offset = offset * Sector.SIZE
        if new_offset != self.offset:
            self.offset = new_offset
            self.data.seek(self.offset)

    def read_sector(self) -> Optional[Sector]:
        """
        Read one sector from the disc

        :return: The sector that was read, or None if the disc image was at EOF
        """
        result = self.data.read(Sector.SIZE)
        self.offset += len(result)
        return Sector(result) if result else None

    def read_sectors(self, num_sectors: int) -> list[Sector]:
        """
        Read multiple sectors from the disc

        :param num_sectors: Number of sectors to read
        :return: The list of sectors that were read. This may be less than the number requested if EOF was reached.
        """
        result = self.data.read(Sector.SIZE*num_sectors)
        size = len(result)
        self.offset += size
        return [Sector(result[i:i+Sector.SIZE]) for i in range(0, size, Sector.SIZE)]

    def write_sector(self, sector: Sector):
        """Write a given sector to the disc"""
        self.data.write(sector.raw)
        self.offset += Sector.SIZE

    @property
    def num_sectors(self) -> int:
        """The number of whole sectors in the disc image"""
        start = self.data.tell()
        self.data.seek(0, 2)
        end = self.data.tell()
        self.data.seek(start)
        return end // Sector.SIZE
