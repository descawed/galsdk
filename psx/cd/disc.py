from __future__ import annotations

from array import array
from enum import IntEnum
from typing import BinaryIO, ByteString, ClassVar, Sequence


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


class EdcTable:
    MAGIC = 0xD8018001

    table: ClassVar[array] = None

    def __get__(self, instance, owner) -> Sequence[int]:
        if EdcTable.table is not None:
            return EdcTable.table

        table = array('I')

        for i in range(256):
            for j in range(8):
                had_carry = i & 1 != 0
                i >>= 1
                if had_carry:
                    i ^= self.MAGIC
            table.append(i)

        EdcTable.table = table
        return table


class Sector:
    """A single sector of a Disc"""
    SIZE = 2352
    SYNC_HEADER = b'\0\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\0'

    edc_table = EdcTable()

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
        self.edit_count = 0
        self.need_error_code_update = False
        if raw is None:
            self._raw = bytearray(Sector.SIZE)
            self._raw[:len(self.SYNC_HEADER)] = self.SYNC_HEADER
            with self:
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

    @staticmethod
    def from_bcd(value: int) -> int:
        out = 0
        place = 1
        while value > 0:
            digit = value & 0xf
            if digit > 9:
                raise ValueError(f'{value:X} is not a valid binary-coded decimal number')
            out += digit * place
            place *= 10
            value >>= 4
        return out

    @staticmethod
    def to_bcd(value: int) -> int:
        out = 0
        shift = 0
        while value > 0:
            digit = value % 10
            out |= digit << shift
            shift += 4
            value //= 10
        return out

    def __enter__(self):
        # this is not thread-safe
        self.edit_count += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.edit_count -= 1
        if self.need_error_code_update:
            # we do the update here even if edit_count isn't 0 so that nested `with` blocks can still expect the error
            # codes to be updated when the block ends
            self.update_edc()
            self.need_error_code_update = False

    def calculate_edc(self) -> int:
        match self.mode:
            case 0:
                return 0
            case 1:
                start = 0
                end = 0x180
            case 2 if self.form == 1:
                start = 0x10
                end = 0x818
            case 2:
                start = 0x10
                end = 0x92c
            case _:
                raise ValueError(f'Invalid mode {self.mode}; expected 0, 1, or 2')

        edc_table = self.edc_table
        edc = 0
        for b in self._raw[start:end]:
            edc ^= b
            edc = (edc >> 8) ^ edc_table[edc & 0xff]
        return edc

    def update_edc(self, force: bool = False):
        # mode 0 sectors have no EDC
        if self.mode == 0:
            return

        # EDC is optional for mode 2/form 2, so if we don't have one already, don't bother setting it unless it was
        # explicitly requested
        if not force and self.mode == 2 and self.form == 2 and self.edc == 0:
            return

        self.edc = self.calculate_edc()

    def validate_edc(self) -> bool:
        edc = self.edc
        # EDC is optional for mode 2/form 2
        if self.mode == 2 and self.form == 2 and edc == 0:
            return True

        return edc == self.calculate_edc()

    def request_error_code_update(self):
        if self.edit_count > 0:
            # if we're in a with block, defer the error code update
            self.need_error_code_update = True
            return

        self.update_edc()
        self.need_error_code_update = False

    @property
    def raw(self) -> bytes:
        return bytes(self._raw)

    @property
    def minute(self) -> int:
        return self.from_bcd(self._raw[0xc])

    @minute.setter
    def minute(self, value: int):
        self._raw[0xc] = self.to_bcd(value)
        if self.mode == 1:
            self.request_error_code_update()

    @property
    def second(self) -> int:
        return self.from_bcd(self._raw[0xd])

    @second.setter
    def second(self, value: int):
        self._raw[0xd] = self.to_bcd(value)
        if self.mode == 1:
            self.request_error_code_update()

    @property
    def sector(self) -> int:
        return self.from_bcd(self._raw[0xe])

    @sector.setter
    def sector(self, value: int):
        self._raw[0xe] = self.to_bcd(value)
        if self.mode == 1:
            self.request_error_code_update()

    @property
    def mode(self) -> int:
        return self._raw[0xf]

    @mode.setter
    def mode(self, value: int):
        old_mode = self.mode
        self._raw[0xf] = value
        if old_mode != value:
            self.request_error_code_update()

    @property
    def file_number(self) -> int | None:
        return self._raw[0x10] if self.mode == 2 else None

    @file_number.setter
    def file_number(self, value: int):
        if self.mode != 2:
            raise AttributeError(f'Cannot set file number on a mode {self.mode} sector')
        self._raw[0x10] = self._raw[0x14] = value
        self.request_error_code_update()

    @property
    def channel(self) -> int | None:
        return self._raw[0x11] if self.mode == 2 else None

    @channel.setter
    def channel(self, value: int):
        if self.mode != 2:
            raise AttributeError(f'Cannot set channel on a mode {self.mode} sector')
        self._raw[0x11] = self._raw[0x15] = value
        self.request_error_code_update()

    @property
    def sub_mode(self) -> int | None:
        return self._raw[0x12] if self.mode == 2 else None

    @sub_mode.setter
    def sub_mode(self, value: int):
        if self.mode != 2:
            raise AttributeError(f'Cannot set sub-mode on a mode {self.mode} sector')
        self._raw[0x12] = self._raw[0x16] = value
        self.request_error_code_update()

    @property
    def coding_info(self) -> int | None:
        return self._raw[0x13] if self.mode == 2 else None

    @coding_info.setter
    def coding_info(self, value: int):
        if self.mode != 2:
            raise AttributeError(f'Cannot set coding info on a mode {self.mode} sector')
        self._raw[0x13] = self._raw[0x17] = value
        self.request_error_code_update()

    @property
    def form(self) -> int | None:
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
        self.request_error_code_update()

    @property
    def edc(self) -> int:
        match self.mode:
            case 0:
                return 0
            case 1:
                return int.from_bytes(self._raw[0x810:0x814], 'little')
            case 2 if self.form == 1:
                return int.from_bytes(self._raw[0x818:0x81c], 'little')
            case 2:
                return int.from_bytes(self._raw[0x92c:0x930], 'little')
            case _:
                raise ValueError(f'Invalid mode {self.mode}; expected 0, 1, or 2')

    @edc.setter
    def edc(self, edc: int):
        edc_bytes = edc.to_bytes(4, 'little')
        match self.mode:
            case 0:
                raise AttributeError('Cannot set EDC on a mode 0 sector')
            case 1:
                self._raw[0x810:0x814] = edc_bytes
            case 2 if self.form == 1:
                self._raw[0x818:0x81c] = edc_bytes
            case 2:
                self._raw[0x92c:0x930] = edc_bytes
            case _:
                raise ValueError(f'Invalid mode {self.mode}; expected 0, 1, or 2')

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
        self._raw[0xf:] = other._raw[0xf:]
        # we don't bother updating error codes for mode 2/form 2 sectors because the EDC doesn't include the part of
        # the sector that was retained from the original sector. this assumes that the EDC of the sector being copied,
        # if present, was already correct.
        if self.mode != 2 or self.form != 2:
            self.request_error_code_update()


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
        return self

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

    def read_sector(self) -> Sector | None:
        """
        Read one sector from the disc

        :return: The sector that was read, or None if the disc image was at EOF
        """
        result = self.data.read(Sector.SIZE)
        self.offset += len(result)
        return Sector(result) if result else None

    def read_sectors(self, num_sectors: int = None) -> list[Sector]:
        """
        Read multiple sectors from the disc

        :param num_sectors: Number of sectors to read. If None, read to EOF.
        :return: The list of sectors that were read. This may be less than the number requested if EOF was reached.
        """
        if num_sectors is None:
            result = self.data.read()
        else:
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
