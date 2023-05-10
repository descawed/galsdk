from __future__ import annotations

import json
import re
import struct
from dataclasses import dataclass, field
from enum import IntEnum, IntFlag
from pathlib import Path
from typing import Any, BinaryIO, Self, TextIO

import rabbitizer

from galsdk.format import FileFormat
from galsdk.game import REGION_ADDRESSES, GameStateOffsets
from galsdk.model import ACTORS


class ColliderType(IntEnum):
    WALL = 0
    RECTANGLE = 1
    TRIANGLE = 2
    CIRCLE = 3


class TriggerType(IntEnum):
    ALWAYS = 0
    NOT_ATTACKING = 1
    ON_ACTIVATE = 2
    ON_SCAN_WITH_LIQUID_EXPLOSIVE = 3
    ON_SCAN = 4
    ON_SCAN_WITH_ITEM = 5
    ON_USE_ITEM = 6


class TriggerFlag(IntFlag):
    ACTOR_1 = 1
    ACTOR_2 = 2
    ACTOR_3 = 4
    ALLOW_LIVING_ACTOR = 8


@dataclass
class Entrance:
    room_index: int
    x: int
    y: int
    z: int
    angle: int


@dataclass
class EntranceSet:
    address: int = 0
    entrances: list[Entrance] = field(default_factory=list)


@dataclass
class ActorInstance:
    id: int
    type: int
    x: int
    y: int
    z: int
    unknown1: int
    orientation: int
    unknown2: int


@dataclass
class ActorLayout:
    name: str
    unknown: bytes
    actors: list[ActorInstance]


@dataclass
class ActorLayoutSet:
    address: int = 0
    layouts: list[ActorLayout] = field(default_factory=list)


@dataclass
class Trigger:
    enabled_callback: int
    type: TriggerType
    flags: TriggerFlag
    item_id: int
    trigger_callback: int
    unknown: int = 0


@dataclass
class TriggerSet:
    address: int = 0
    triggers: list[Trigger] = field(default_factory=list)


@dataclass
class BackgroundMask:
    index: int
    unknown1: int
    x: int
    y: int
    z: int
    unknown2: int


@dataclass
class Background:
    index: int
    mask_address: int
    masks: list[BackgroundMask]


@dataclass
class BackgroundSet:
    address: int = 0
    backgrounds: list[Background] = field(default_factory=list)


@dataclass
class Collider:
    type: ColliderType
    element_ptr: int
    unknown: int


@dataclass
class RectangleCollider:
    x_pos: int
    z_pos: int
    x_size: int
    z_size: int
    unknown: int = 0xf


@dataclass
class TriangleCollider:
    x1: int
    z1: int
    x2: int
    z2: int
    x3: int
    z3: int


@dataclass
class CircleCollider:
    x: int
    z: int
    radius: int


@dataclass
class Camera:
    orientation: int
    vertical_fov: int
    scale: int
    x: int
    y: int
    z: int
    target_x: int
    target_y: int
    target_z: int
    unknown: int


@dataclass
class CameraCut:
    index: int
    x1: int
    z1: int
    x2: int
    z2: int
    x3: int
    z3: int
    x4: int
    z4: int


@dataclass
class Interactable:
    id: int
    x_pos: int
    z_pos: int
    x_size: int
    z_size: int


@dataclass
class RoomLayout:
    address: int = 0
    colliders: list[Collider] = field(default_factory=lambda: [])
    rectangle_colliders: list[RectangleCollider] = field(default_factory=lambda: [])
    triangle_colliders: list[TriangleCollider] = field(default_factory=lambda: [])
    circle_colliders: list[CircleCollider] = field(default_factory=lambda: [])
    cameras: list[Camera] = field(default_factory=lambda: [])
    cuts: list[CameraCut] = field(default_factory=lambda: [])
    interactables: list[Interactable] = field(default_factory=lambda: [])


class Undefined:
    def __abs__(self) -> Undefined:
        return self

    def __add__(self, other: Any) -> Undefined:
        return self

    def __sub__(self, other: Any) -> Undefined:
        return self

    def __mul__(self, other: Any) -> Undefined:
        return self

    def __truediv__(self, other: Any) -> Undefined:
        return self

    def __floordiv__(self, other: Any) -> Undefined:
        return self

    def __neg__(self) -> Undefined:
        return self

    def __pos__(self) -> Undefined:
        return self

    def __and__(self, other: Any) -> Undefined:
        return self

    def __or__(self, other: Any) -> Undefined:
        return self

    def __xor__(self, other: Any) -> Undefined:
        return self

    def __eq__(self, other: Any) -> bool:
        return False

    def __ne__(self, other: Any) -> bool:
        return False


UNDEFINED = Undefined()


@dataclass
class RoomAddresses:
    game_state: int
    set_room_layout: int
    actor_layouts: set[int] = field(default_factory=set)
    triggers: set[int] = field(default_factory=set)
    backgrounds: set[int] = field(default_factory=set)
    room_layout: set[int] = field(default_factory=set)
    entrances: set[int] = field(default_factory=set)
    num_entrances: int = 0

    @property
    def is_valid(self) -> bool:
        return len(self.actor_layouts) > 0 and len(self.backgrounds) > 0 and len(self.room_layout) > 0

    @property
    def is_complete(self) -> bool:
        return self.is_valid and len(self.triggers) > 0

    def set_by_address(self, address: int, value: int):
        if address == self.game_state + GameStateOffsets.ACTOR_LAYOUTS:
            self.actor_layouts.add(value)
        elif address == self.game_state + GameStateOffsets.BACKGROUNDS:
            self.backgrounds.add(value)
        elif address == self.game_state + GameStateOffsets.TRIGGERS:
            self.triggers.add(value)

    def get_by_address(self, address: int) -> int | Undefined:
        if address == self.game_state + GameStateOffsets.ACTOR_LAYOUTS:
            return next(iter(self.actor_layouts))
        elif address == self.game_state + GameStateOffsets.BACKGROUNDS:
            return next(iter(self.backgrounds))
        elif address == self.game_state + GameStateOffsets.TRIGGERS:
            return next(iter(self.triggers))

        return UNDEFINED

    def is_last_room_address(self, address: int | Undefined) -> bool:
        return address == self.game_state + GameStateOffsets.LAST_ROOM


class RoomModule(FileFormat):
    ACTOR_INSTANCE_SIZE = 16
    ACTOR_LAYOUT_SIZE = 100
    MAX_ACTORS = 4
    MAX_ADDRESS = 0x801FFFFF
    MAX_CAMERAS = 10
    MAX_ITEM_ID = 38
    MAX_REGIONS = 100
    MIN_ADDRESS = 0x80000000
    NAME_REGEX = re.compile(rb'[ABCD]\d{2}[0-9A-Z]{2}')
    ROOM_LAYOUT_SIZE = 0x2d5c
    TRIGGER_SIZE = 16

    def __init__(self, module_id: int, layout: RoomLayout, backgrounds: list[BackgroundSet],
                 actor_layouts: list[ActorLayoutSet], triggers: TriggerSet, entrances: EntranceSet, load_address: int):
        self.module_id = module_id
        self.layout = layout
        self.backgrounds = backgrounds
        self.actor_layouts = actor_layouts
        self.triggers = triggers
        self.entrances = entrances
        self.load_address = load_address

    @property
    def is_empty(self) -> bool:
        return len(self.layout.cameras) == 0 and len(self.backgrounds) == 0 and len(self.actor_layouts) == 0 and \
               len(self.triggers.triggers) == 0

    @property
    def is_stub(self) -> bool:
        return self.module_id != 0 and self.is_empty

    @property
    def is_valid(self) -> bool:
        return len(self.actor_layouts) > 0 and len(self.backgrounds) > 0 and \
               len(self.layout.cameras) > 0

    @property
    def name(self) -> str | None:
        try:
            return self.actor_layouts[0].layouts[0].name
        except IndexError:
            return None

    @property
    def suggested_extension(self) -> str:
        return '.RMD'

    @classmethod
    def import_(cls, path: Path, fmt: str = None) -> Self:
        raise NotImplementedError

    def export(self, path: Path, fmt: str = None) -> Path:
        raise NotImplementedError

    @classmethod
    def sniff(cls, f: BinaryIO) -> Self | None:
        for addresses in REGION_ADDRESSES.values():
            f.seek(0)
            try:
                module = cls.load(f, addresses['ModuleLoadAddresses'][0])
                if module.is_valid:
                    return module
            except Exception:
                pass
        return None

    @classmethod
    def read(cls, f: BinaryIO, *, language: str = None, entry_point: int = None, **kwargs) -> Self:
        if language is None:
            # we'll just have to guess what the address is
            module = cls.sniff(f)
            if module is None:
                raise ValueError('Provided file does not appear to be a room module')
            return None
        if entry_point is None:
            return cls.load(f, REGION_ADDRESSES[language]['ModuleLoadAddresses'][0])
        return cls.parse(f, language, entry_point)

    def write(self, f: BinaryIO, **kwargs):
        raise NotImplementedError

    def save_metadata(self, f: TextIO):
        json.dump({
            'loadAddress': self.load_address,
            'actorLayouts': [layout_set.address + self.load_address for layout_set in self.actor_layouts],
            'roomLayout': self.layout.address + self.load_address,
            'backgrounds': [background_set.address + self.load_address for background_set in self.backgrounds],
            'triggers': self.triggers.address + self.load_address,
            'entrances': self.entrances.address + self.load_address,
            'numEntrances': len(self.entrances.entrances),
        }, f)

    @classmethod
    def load_with_metadata(cls, path: Path) -> RoomModule:
        meta_path = path.with_suffix('.json')
        with meta_path.open() as f:
            metadata = json.load(f)

        load_address = metadata['loadAddress']
        room_addresses = RoomAddresses(0, 0, set(metadata['actorLayouts']), {metadata['triggers']},
                                       set(metadata['backgrounds']), {metadata['roomLayout']}, {metadata['entrances']},
                                       metadata['numEntrances'])

        data = path.read_bytes()
        return cls.parse_with_addresses(data, load_address, room_addresses)

    @classmethod
    def _is_ptr(cls, p: int) -> bool:
        return p == 0 or cls.MIN_ADDRESS <= p <= cls.MAX_ADDRESS

    @classmethod
    def parse_entrances(cls, data: bytes, address: int, num_entrances: int) -> EntranceSet:
        entrance_set = EntranceSet(address)
        for _ in range(num_entrances):
            entrance_set.entrances.append(Entrance(*struct.unpack_from('<4hi', data, address)))
            address += 12
        return entrance_set

    @classmethod
    def parse_actor_layout(cls, data: bytes, address: int) -> ActorLayoutSet:
        actor_layout_set = ActorLayoutSet(address)

        while True:
            layout_data = data[address:address + cls.ACTOR_LAYOUT_SIZE]
            raw_name = layout_data[:6].rstrip(b'\0')
            if not cls.NAME_REGEX.match(raw_name):
                break
            name = raw_name.decode()
            unknown = layout_data[6:0x24]
            instances = []
            for i in range(cls.MAX_ACTORS):
                start = 0x24 + i * cls.ACTOR_INSTANCE_SIZE
                instances.append(ActorInstance(*struct.unpack_from('<H4h3H', layout_data, start)))
            actor_layout_set.layouts.append(ActorLayout(name, unknown, instances))
            address += cls.ACTOR_LAYOUT_SIZE

        return actor_layout_set

    @classmethod
    def parse_room_layout(cls, data: bytes, address: int, known_good: bool = False) -> RoomLayout:
        max_colliders = cls.MAX_REGIONS * 3  # rectangle (includes wall), triangle, circle
        collider_count = int.from_bytes(data[address:address + 4], 'little')
        if collider_count > max_colliders or (collider_count == 0 and not known_good):
            # invalid number of colliders; this isn't it
            raise ValueError('Invalid collider count')

        # reset the room layout from any previous aborted parsing attempt
        room_layout = RoomLayout(address)

        offset = address + 4
        num_rects = num_tris = num_circles = 0
        for _ in range(collider_count):
            collider_type = ColliderType(int.from_bytes(data[offset:offset + 4], 'little'))
            match collider_type:
                case ColliderType.TRIANGLE:
                    num_tris += 1
                case ColliderType.CIRCLE:
                    num_circles += 1
                case _:
                    num_rects += 1
            element_ptr = int.from_bytes(data[offset + 4:offset + 8], 'little')
            # TODO: this might be an angle; see main function in D0003
            unknown = int.from_bytes(data[offset + 8:offset + 12], 'little')
            room_layout.colliders.append(Collider(collider_type, element_ptr, unknown))
            offset += 12

        if num_rects > cls.MAX_REGIONS or num_tris > cls.MAX_REGIONS or num_circles > cls.MAX_REGIONS:
            raise ValueError('Too many collider shapes')

        # these are fixed-size arrays (size = MAX_REGIONS), which is why we manually calculate the offset after
        # reading the elements that are actually present
        offset = address + 0x4b4
        for _ in range(num_rects):
            room_layout.rectangle_colliders.append(RectangleCollider(*struct.unpack_from('<5i', data, offset)))
            offset += 20

        offset = address + 0xc84
        for _ in range(num_tris):
            room_layout.triangle_colliders.append(TriangleCollider(*struct.unpack_from('<6i', data, offset)))
            offset += 24

        offset = address + 0x15e4
        for _ in range(num_circles):
            room_layout.circle_colliders.append(CircleCollider(*struct.unpack_from('<3i', data, offset)))
            offset += 12

        offset = address + 0x1a94
        num_cameras = int.from_bytes(data[offset:offset + 4], 'little')
        if num_cameras > cls.MAX_CAMERAS or (num_cameras == 0 and not known_good):
            raise ValueError('Invalid number of cameras')

        offset += 4
        for _ in range(num_cameras):
            room_layout.cameras.append(Camera(*struct.unpack_from('<10h', data, offset)))
            offset += 20

        offset = address + 0x1b60
        while True:
            marker = int.from_bytes(data[offset:offset + 2], 'little', signed=True)
            if marker < 0:
                break

            room_layout.cuts.append(CameraCut(*struct.unpack_from('<h8i', data, offset + 2)))
            offset += 0x24

        offset = address + 0x2970
        num_interactables = int.from_bytes(data[offset:offset + 4], 'little')
        if num_interactables > cls.MAX_REGIONS:
            raise ValueError('Invalid number of interactables')

        offset += 4
        for _ in range(num_interactables):
            room_layout.interactables.append(Interactable(*struct.unpack_from('<5h', data, offset)))
            offset += 10

        return room_layout

    @classmethod
    def parse_backgrounds(cls, data: bytes, address: int, num_backgrounds: int, load_address: int,
                          known_good: bool = False) -> BackgroundSet:
        backgrounds = BackgroundSet(address)
        offset = address
        for _ in range(num_backgrounds):
            index = int.from_bytes(data[offset:offset + 2], 'little', signed=True)
            num_masks = int.from_bytes(data[offset + 2:offset + 4], 'little')
            mask_ptr = int.from_bytes(data[offset + 4:offset + 8], 'little')

            if index == -1:
                # not present; happens for some camera angles that are never actually used
                background = Background(-1, 0, [])
            else:
                # find masks
                mask_offset = mask_ptr - load_address
                if mask_offset < 0 or mask_offset >= len(data):
                    if known_good:
                        background = Background(-1, 0, [])
                    else:
                        raise ValueError
                else:
                    background = Background(index, mask_ptr, [])
                    for _ in range(num_masks):
                        background.masks.append(BackgroundMask(*struct.unpack_from('<2I4h', data, mask_offset)))
                        mask_offset += 16

            backgrounds.backgrounds.append(background)
            offset += 8

        return backgrounds

    @classmethod
    def parse_triggers(cls, data: bytes, address: int, num_triggers: int, known_good: bool = False) -> TriggerSet:
        triggers = TriggerSet(address)
        offset = address

        for _ in range(num_triggers):
            try:
                enabled_callback = int.from_bytes(data[offset:offset + 4], 'little')
                if not cls._is_ptr(enabled_callback):
                    raise ValueError
                trigger_type = TriggerType(data[offset + 4])
                flags = TriggerFlag(data[offset + 5])
                item_id = int.from_bytes(data[offset + 6:offset + 8], 'little')
                if item_id > cls.MAX_ITEM_ID:
                    raise ValueError
                trigger_callback = int.from_bytes(data[offset + 8:offset + 12], 'little')
                if trigger_callback == 0 or not cls._is_ptr(trigger_callback):
                    raise ValueError
                unknown = int.from_bytes(data[offset + 12:offset + 16], 'little')
                triggers.triggers.append(Trigger(enabled_callback, trigger_type, flags, item_id,
                                                 trigger_callback, unknown))
            except ValueError:
                if known_good:
                    break
                else:
                    raise
            offset += cls.TRIGGER_SIZE

        return triggers

    @staticmethod
    def find_entrance_count(data: bytes, start_address: int, module_space: range) -> int:
        for i in range(start_address, module_space.stop, 4):
            offset = i - module_space.start
            word = int.from_bytes(data[offset:offset + 4], 'little')
            inst = rabbitizer.Instruction(word, i)
            if not inst.isValid():
                return 0
            if inst.isBranch() or inst.isJump():
                # we've gone too far and hit the end of the loop; give up
                return 0
            if inst.getOpcodeName() == 'slti':
                return inst.getProcessedImmediate()

    @classmethod
    def parse_function(cls, data: bytes, start_address: int, module_space: range, room_address: RoomAddresses,
                       regs: list[Undefined | int]):
        in_delay_slot = False
        jump_address = None
        do_return = False
        restore_regs = False
        grab_room_layout_ptr = False
        found_entrance_array = False
        sources: list[Undefined | int] = [UNDEFINED for _ in regs]

        for i in range(start_address, module_space.stop, 4):
            offset = i - module_space.start
            word = int.from_bytes(data[offset:offset+4], 'little')
            inst = rabbitizer.Instruction(word, i)
            if not inst.isValid():
                raise ValueError(f'Invalid instruction at address {i:08X}')

            match inst.getOpcodeName():
                case 'lui':
                    regs[inst.rt.value] = inst.getProcessedImmediate() << 16
                    sources[inst.rt.value] = UNDEFINED
                case 'addiu':
                    regs[inst.rt.value] = regs[inst.rs.value] + inst.getProcessedImmediate()
                    sources[inst.rt.value] = UNDEFINED
                case 'addu':
                    regs[inst.rd.value] = regs[inst.rs.value] + regs[inst.rt.value]
                    sources[inst.rd.value] = UNDEFINED
                case 'jal':
                    dest = inst.getInstrIndexAsVram()
                    in_delay_slot = True
                    if dest in module_space:
                        jump_address = dest
                    elif dest == room_address.set_room_layout:
                        grab_room_layout_ptr = True
                    continue
                case 'jr':
                    in_delay_slot = True
                    do_return = inst.isJrRa()
                    continue
                case 'sw':
                    address = regs[inst.rs.value] + inst.getProcessedImmediate()
                    value = regs[inst.rt.value]
                    if address is not UNDEFINED and value is not UNDEFINED and value in module_space:
                        room_address.set_by_address(address, value)
                        if room_address.is_complete:
                            return  # nothing left to do
                case 'lw':
                    address = regs[inst.rs.value] + inst.getProcessedImmediate()
                    if address is not UNDEFINED:
                        regs[inst.rt.value] = room_address.get_by_address(address)
                        sources[inst.rt.value] = address
                case 'lh':
                    address = regs[inst.rs.value] + inst.getProcessedImmediate()
                    if address is not UNDEFINED:
                        regs[inst.rt.value] = room_address.get_by_address(address) & 0xffff
                        sources[inst.rt.value] = address
                case _:
                    if (is_branch := inst.isBranch()) and inst.readsRt() and inst.readsRs():
                        # first, check if we're comparing to the game state's lastRoom field; that will identify if this
                        # value came from the room's entrance array
                        had_found_entrance_array = found_entrance_array
                        if (room_address.is_last_room_address(sources[inst.rt.value])
                                and sources[inst.rs.value] is not UNDEFINED):
                            room_address.entrances.add(sources[inst.rs.value])
                            found_entrance_array = True
                        elif (room_address.is_last_room_address(sources[inst.rs.value])
                              and sources[inst.rt.value] is not UNDEFINED):
                            room_address.entrances.add(sources[inst.rt.value])
                            found_entrance_array = True

                        # for some reason, this function can return a signed number, so do the two's complement
                        dest = (inst.getBranchVramGeneric() + (1 << 32)) & 0xffffffff
                        if had_found_entrance_array != found_entrance_array:
                            # if we just found the entrance array, try to follow the branch and see if it leads us to
                            # the condition checking the count
                            room_address.num_entrances = cls.find_entrance_count(data, dest, module_space)

                    if is_branch or inst.isJump():
                        # for some reason, this function can return a signed number, so do the two's complement
                        dest = (inst.getBranchVramGeneric() + (1 << 32)) & 0xffffffff

                        # we only care about forward branches because we don't want to revisit code we've already seen
                        if dest > i:
                            in_delay_slot = True
                            jump_address = dest
                            restore_regs = True
                            continue
                        elif inst.isUnconditionalBranch():
                            # if we encounter an unconditional backwards branch, exit this code path
                            in_delay_slot = True
                            do_return = True
                            continue

                    # wipe out any registers modified by instructions we don't know about
                    if inst.modifiesRt():
                        regs[inst.rt.value] = UNDEFINED
                        sources[inst.rt.value] = UNDEFINED
                    if inst.modifiesRd():
                        regs[inst.rd.value] = UNDEFINED
                        sources[inst.rd.value] = UNDEFINED
                    if inst.modifiesRs():
                        regs[inst.rs.value] = UNDEFINED
                        sources[inst.rs.value] = UNDEFINED

            if in_delay_slot:
                in_delay_slot = False

                if grab_room_layout_ptr:
                    room_layout_ptr = regs[rabbitizer.RegGprO32.a2.value]
                    if room_layout_ptr is not UNDEFINED and room_layout_ptr in module_space:
                        room_address.room_layout.add(room_layout_ptr)
                    else:
                        raise ValueError('Found call to SetRoomLayout but a2 was undefined')
                    if room_address.is_complete:
                        return  # nothing left to do

                if jump_address is not None:
                    regs_to_restore = [reg for reg in regs]
                    cls.parse_function(data, jump_address, module_space, room_address, regs)
                    if room_address.is_complete:
                        # we've found everything we were looking for; no need to keep parsing
                        return

                    jump_address = None
                    if restore_regs:
                        regs = regs_to_restore
                        restore_regs = False
                elif do_return:
                    return
                else:
                    # clobber registers
                    for j in range(1, len(regs)):
                        if not rabbitizer.RegGprO32.s0.value <= j <= rabbitizer.RegGprO32.s7.value:
                            regs[j] = UNDEFINED
                            sources[j] = UNDEFINED

    @classmethod
    def parse_with_addresses(cls, data: bytes, load_address: int, room_addresses: RoomAddresses) -> RoomModule:
        module_id = int.from_bytes(data[:4], 'little')

        actor_layouts = []
        used_ranges = []
        for al_address in sorted(room_addresses.actor_layouts):
            offset = al_address - load_address
            if any(offset in used_range for used_range in used_ranges):
                continue  # we got this one already
            layouts = cls.parse_actor_layout(data, offset)
            used_ranges.append(range(offset, offset + len(layouts.layouts) * cls.ACTOR_LAYOUT_SIZE))
            actor_layouts.append(layouts)

        if len(room_addresses.room_layout) != 1:
            raise ValueError('Unexpected number of room layouts')

        offset = room_addresses.room_layout.pop() - load_address
        room_layout = cls.parse_room_layout(data, offset, True)

        backgrounds = []
        for address in room_addresses.backgrounds:
            offset = address - load_address
            backgrounds.append(cls.parse_backgrounds(data, offset, len(room_layout.cameras), load_address, True))

        if len(room_addresses.triggers) != 1:
            raise ValueError('Unexpected number of trigger sets')

        offset = room_addresses.triggers.pop() - load_address
        triggers = cls.parse_triggers(data, offset, len(room_layout.interactables), True)

        if len(room_addresses.entrances) > 1:
            raise ValueError('Too many entrance sets')
        elif len(room_addresses.entrances) == 1:
            offset = room_addresses.entrances.pop() - load_address
            entrance_set = cls.parse_entrances(data, offset, room_addresses.num_entrances)
        else:
            entrance_set = EntranceSet()

        return cls(module_id, room_layout, backgrounds, actor_layouts, triggers, entrance_set, load_address)

    @classmethod
    def parse(cls, f: BinaryIO, language: str, entry_point: int) -> RoomModule:
        data = f.read()
        module_id = int.from_bytes(data[:4], 'little')

        addresses = REGION_ADDRESSES[language]
        load_address = addresses['ModuleLoadAddresses'][0]

        if (entry_point - load_address) >= len(data):
            # this is a stub; return a dummy module
            return cls(module_id, RoomLayout(), [], [], TriggerSet(), EntranceSet(), load_address)

        game_state = addresses['GameState']
        regs: list[Undefined | int] = [UNDEFINED] * 32
        regs[0] = 0
        regs[rabbitizer.RegGprO32.a0.value] = game_state
        room_addresses = RoomAddresses(game_state, addresses['SetRoomLayout'])
        cls.parse_function(data, entry_point, range(load_address, load_address + len(data)), room_addresses, regs)
        if not room_addresses.is_valid:
            raise ValueError('Failed to parse room structure')

        return cls.parse_with_addresses(data, load_address, room_addresses)

    @classmethod
    def load(cls, f: BinaryIO, load_address: int) -> RoomModule:
        data = f.read()
        module_id = int.from_bytes(data[:4], 'little')

        # the rest of the module is just a binary blob, so we have to heuristically search for the data structures we're
        # interested in
        # start by recording which addresses are used by other stuff
        used_addresses = [range(4)]

        # look for the actor layouts, which can be identified by regex
        actor_layouts = []
        for match in cls.NAME_REGEX.finditer(data):
            address = match.start()
            if any(address in region for region in used_addresses):
                # we already have this one
                continue

            actor_layout_set = cls.parse_actor_layout(data, address)
            actor_layouts.append(actor_layout_set)
            if actor_layout_set.address > 0:
                used_addresses.append(
                    range(actor_layout_set.address,
                          actor_layout_set.address + len(actor_layout_set.layouts) * cls.ACTOR_LAYOUT_SIZE)
                )

        # next, look for room layout. we'll assume it's aligned on a 4-byte boundary
        room_layout = RoomLayout()
        for i in range(0, len(data), 4):
            if any(i in region for region in used_addresses):
                continue

            try:
                room_layout = cls.parse_room_layout(data, i)
                room_layout.address = i
                break
            except (ValueError, struct.error):
                pass

        if room_layout.address > 0:
            used_addresses.append(range(room_layout.address, room_layout.address + cls.ROOM_LAYOUT_SIZE))

        # next, look for trigger callbacks
        num_triggers = len(room_layout.interactables)
        triggers = TriggerSet()
        if num_triggers > 0:
            for i in range(0, len(data), 4):
                if any(i in region for region in used_addresses):
                    continue

                try:
                    triggers = cls.parse_triggers(data, i, num_triggers)
                    triggers.address = i
                    break
                except (IndexError, ValueError):
                    pass

        if triggers.address > 0:
            used_addresses.append(range(triggers.address, triggers.address + num_triggers * cls.TRIGGER_SIZE))

        # finally, look for background image definitions
        backgrounds = BackgroundSet()
        num_backgrounds = len(room_layout.cameras)
        if num_backgrounds > 0:
            for i in range(0, len(data), 4):
                if any(i in region for region in used_addresses):
                    continue

                try:
                    backgrounds = cls.parse_backgrounds(data, i, num_backgrounds, load_address)
                    backgrounds.address = i
                    break
                except (IndexError, ValueError, struct.error):
                    pass

        return cls(module_id, room_layout, [backgrounds], actor_layouts, triggers, EntranceSet(), load_address)


def dump_info(module_path: str, language: str | None, force: bool, entry_point: int = None):
    guessed = ''
    with open(module_path, 'rb') as f:
        if language is None:
            module = RoomModule.sniff(f)
            guessed = ' (guessed)'
        elif entry_point is None:
            module = RoomModule.load(f, REGION_ADDRESSES[language]['ModuleLoadAddresses'][0])
        else:
            module = RoomModule.parse(f, language, entry_point)

    if module is None or not (force or module.is_valid):
        print(f'{module_path} does not appear to be a Galerians room module')
        return

    language = 'unknown'
    for addr_lang, addresses in REGION_ADDRESSES.items():
        if addresses['ModuleLoadAddresses'][0] == module.load_address:
            language = addr_lang
            break

    print(f'Name: {module.name}')
    print(f'Load address{guessed}: {module.load_address:08X} ({language})')

    print(f'Room layout: {module.layout.address:08X}')
    print('\tColliders:')
    for i, collider in enumerate(module.layout.colliders):
        print(f'\t\tCollider {i}')
        print(f'\t\t\tType: {collider.type}')
        print(f'\t\t\tElement pointer: {collider.element_ptr:08X}')
        print(f'\t\t\tUnknown: {collider.unknown:08X}')
    print('\tRectangle collider bounds:')
    for i, rect in enumerate(module.layout.rectangle_colliders):
        print(f'\t\tRectangle {i}')
        print(f'\t\t\tX: {rect.x_pos}')
        print(f'\t\t\tZ: {rect.z_pos}')
        print(f'\t\t\tX size: {rect.x_size}')
        print(f'\t\t\tZ size: {rect.z_size}')
        print(f'\t\t\tUnknown: {rect.unknown:08X}')
    print('\tTriangle collider bounds:')
    for i, tri in enumerate(module.layout.triangle_colliders):
        print(f'\t\tTriangle {i}')
        print(f'\t\t\tX1: {tri.x1}')
        print(f'\t\t\tZ1: {tri.z1}')
        print(f'\t\t\tX2: {tri.x2}')
        print(f'\t\t\tZ2: {tri.z2}')
        print(f'\t\t\tX3: {tri.x3}')
        print(f'\t\t\tZ3: {tri.z3}')
    print('\tCircle collider bounds:')
    for i, circle in enumerate(module.layout.circle_colliders):
        print(f'\t\tCircle {i}')
        print(f'\t\t\tX: {circle.x}')
        print(f'\t\t\tZ: {circle.z}')
        print(f'\t\t\tRadius: {circle.radius}')
    print('\tCameras:')
    for i, camera in enumerate(module.layout.cameras):
        print(f'\t\tCamera {i}')
        print(f'\t\t\tRotation: {camera.orientation}')
        print(f'\t\t\tVertical FOV: {camera.vertical_fov}')
        print(f'\t\t\tScale: {camera.scale}')
        print(f'\t\t\tX: {camera.x}')
        print(f'\t\t\tY: {camera.y}')
        print(f'\t\t\tZ: {camera.z}')
        print(f'\t\t\tTarget X: {camera.target_x}')
        print(f'\t\t\tTarget Y: {camera.target_y}')
        print(f'\t\t\tTarget Z: {camera.target_z}')
        print(f'\t\t\tUnknown: {camera.unknown:04X}')
    print('\tCamera cuts:')
    for i, cut in enumerate(module.layout.cuts):
        print(f'\t\tCut {i}')
        print(f'\t\t\tBG index: {cut.index}')
        print(f'\t\t\tX1: {cut.x1}')
        print(f'\t\t\tZ1: {cut.z1}')
        print(f'\t\t\tX2: {cut.x2}')
        print(f'\t\t\tZ2: {cut.z2}')
        print(f'\t\t\tX3: {cut.x3}')
        print(f'\t\t\tZ3: {cut.z3}')
        print(f'\t\t\tX4: {cut.x4}')
        print(f'\t\t\tZ4: {cut.z4}')
    print('\tInteractables:')
    for i, interactable in enumerate(module.layout.interactables):
        print(f'\t\tInteractable {i}')
        print(f'\t\t\tID: {interactable.id}')
        print(f'\t\t\tX: {interactable.x_pos}')
        print(f'\t\t\tZ: {interactable.z_pos}')
        print(f'\t\t\tX size: {interactable.x_size}')
        print(f'\t\t\tZ size: {interactable.z_size}')

    print(f'Triggers: {module.triggers.address:08X}')
    for i, trigger in enumerate(module.triggers.triggers):
        print(f'\tTrigger {i}')
        print(f'\t\tEnabled callback: {trigger.enabled_callback:08X}')
        print(f'\t\tType: {trigger.type}')
        print(f'\t\tFlags: {trigger.flags}')
        print(f'\t\tItem ID: {trigger.item_id}')
        print(f'\t\tTrigger callback: {trigger.trigger_callback:08X}')
        print(f'\t\tUnknown: {trigger.unknown:08X}')

    print(f'Entrances: {module.entrances.address:08X}')
    for i, entrance in enumerate(module.entrances.entrances):
        print(f'\tEntrance {i}')
        print(f'\t\tRoom index: {entrance.room_index}')
        print(f'\t\tX: {entrance.x}')
        print(f'\t\tY: {entrance.y}')
        print(f'\t\tZ: {entrance.z}')
        print(f'\t\tAngle: {entrance.angle}')

    print('Backgrounds')
    for i, background_set in enumerate(module.backgrounds):
        print(f'\tBackground set {i}: {background_set.address:08X}')
        for j, background in enumerate(background_set.backgrounds):
            print(f'\t\tBackground {j}')
            print(f'\t\t\tIndex: {background.index}')
            print(f'\t\t\tMask address: {background.mask_address:08X}')
            print('\t\t\tMasks')
            for k, mask in enumerate(background.masks):
                print(f'\t\t\t\tMask {k}')
                print(f'\t\t\t\t\tIndex: {mask.index}')
                print(f'\t\t\t\t\tUnknown 1: {mask.unknown1:08X}')
                print(f'\t\t\t\t\tX: {mask.x}')
                print(f'\t\t\t\t\tY: {mask.y}')
                print(f'\t\t\t\t\tZ: {mask.z}')
                print(f'\t\t\t\t\tUnknown 2: {mask.unknown1:04X}')

    print('Actor layouts')
    for i, layout_set in enumerate(module.actor_layouts):
        print(f'\tLayout set {i}: {layout_set.address:08X}')
        for j, layout in enumerate(layout_set.layouts):
            print(f'\t\tLayout {j}')
            for k, actor in enumerate(layout.actors):
                if 0 <= actor.type < len(ACTORS):
                    actor_name = ACTORS[actor.type].name
                else:
                    actor_name = 'unknown'
                print(f'\t\t\tActor {k}')
                print(f'\t\t\t\tID: {actor.id}')
                print(f'\t\t\t\tType: {actor.type} ({actor_name})')
                print(f'\t\t\t\tX: {actor.x}')
                print(f'\t\t\t\tY: {actor.y}')
                print(f'\t\t\t\tZ: {actor.z}')
                print(f'\t\t\t\tUnknown 1: {actor.unknown1:04X}')
                print(f'\t\t\t\tRotation: {actor.orientation}')
                print(f'\t\t\t\tUnknown 2: {actor.unknown2:04X}')


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Dump information about Galerians room modules')
    parser.add_argument('-l', '--language', help='The language of the game version this room module is from. If not '
                        'provided, we will attempt to guess.', choices=list(REGION_ADDRESSES))
    parser.add_argument('-e', '--entry', help="Address in hexadecimal of the room's startup function. This will help "
                        'parse the module more accurately, but only for game versions supported by the editor.',
                        type=lambda e: int(e, 16))
    parser.add_argument('-f', '--force', help="Dump what data we were able to find even if the file doesn't look like "
                        'a valid room module', action='store_true')
    parser.add_argument('module', help='Path to the room module to examine')

    args = parser.parse_args()
    dump_info(args.module, args.language, args.force, args.entry)
