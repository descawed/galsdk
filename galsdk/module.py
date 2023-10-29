from __future__ import annotations

import json
import re
import struct
from dataclasses import asdict, astuple, dataclass, field, replace
from enum import IntEnum, IntFlag
from pathlib import Path
from typing import Any, BinaryIO, Self, TextIO

import rabbitizer

from galsdk.format import FileFormat
from galsdk.game import REGION_ADDRESSES, KNOWN_FUNCTIONS, ArgumentType, GameStateOffsets
from galsdk.model import ACTORS


class ColliderType(IntEnum):
    WALL = 0
    RECTANGLE = 1
    TRIANGLE = 2
    CIRCLE = 3

    @property
    def unknown(self) -> int:
        return 0x3F if self == ColliderType.WALL else 0x3FF


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
class FunctionCall:
    call_address: int
    name: str
    arguments: list[tuple[int | None, int | None]]
    is_enabled: bool | None = True


@dataclass
class CallbackFunction:
    calls: list[FunctionCall]
    return_value_instruction: int | None
    return_value: int | None


@dataclass
class Entrance:
    room_index: int
    x: int
    y: int
    z: int
    angle: int

    def encode(self) -> bytes:
        return struct.pack('<4hi', *astuple(self))


@dataclass
class EntranceSet:
    address: int = 0
    entrances: list[Entrance] = field(default_factory=list)

    def encode(self) -> bytes:
        return b''.join(entrance.encode() for entrance in self.entrances)


@dataclass
class ActorInstance:
    id: int = 0
    type: int = -1
    x: int = 0
    y: int = 0
    z: int = 0
    unknown1: int = 0
    orientation: int = 0
    unknown2: int = 0

    def encode(self) -> bytes:
        return struct.pack('<H4h3H', *astuple(self))


@dataclass
class ActorLayout:
    name: str
    unknown: bytes
    actors: list[ActorInstance]

    def encode(self) -> bytes:
        return self.name.encode().ljust(6, b'\0') + self.unknown + b''.join(actor.encode() for actor in self.actors)


@dataclass
class ActorLayoutSet:
    address: int = 0
    layouts: list[ActorLayout] = field(default_factory=list)

    def encode(self) -> bytes:
        return b''.join(layout.encode() for layout in self.layouts)


@dataclass
class Trigger:
    enabled_callback: int
    type: TriggerType
    flags: TriggerFlag
    item_id: int
    trigger_callback: int
    unknown: int = 0

    def encode(self) -> bytes:
        return struct.pack('<I2BH2I', *astuple(self))


@dataclass
class TriggerSet:
    address: int = 0
    triggers: list[Trigger] = field(default_factory=list)

    def encode(self) -> bytes:
        return b''.join(trigger.encode() for trigger in self.triggers)


@dataclass
class BackgroundMask:
    index: int
    unknown1: int
    x: int
    y: int
    z: int
    unknown2: int

    def encode(self) -> bytes:
        return struct.pack('<2I4h', *astuple(self))


@dataclass
class Background:
    index: int
    mask_address: int
    masks: list[BackgroundMask]

    def encode(self) -> bytes:
        return struct.pack('<hHI', self.index, len(self.masks), self.mask_address)


@dataclass
class BackgroundSet:
    address: int = 0
    backgrounds: list[Background] = field(default_factory=list)

    def encode(self) -> bytes:
        return b''.join(background.encode() for background in self.backgrounds)


@dataclass
class Collider:
    type: ColliderType
    # this is recalculated by SetRoomObjInfo by iterating through the collider lists, so the actual value in the module
    # doesn't matter
    element_ptr: int
    unknown: int

    def encode(self) -> bytes:
        return struct.pack('<3I', *astuple(self))


@dataclass
class RectangleCollider:
    x_pos: int
    z_pos: int
    x_size: int
    z_size: int
    unknown: int = 0xf

    def encode(self) -> bytes:
        return struct.pack('<5i', *astuple(self))


@dataclass
class TriangleCollider:
    x1: int
    z1: int
    x2: int
    z2: int
    x3: int
    z3: int

    def encode(self) -> bytes:
        return struct.pack('<6i', *astuple(self))


@dataclass
class CircleCollider:
    x: int
    z: int
    radius: int

    def encode(self) -> bytes:
        return struct.pack('<3i', *astuple(self))


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

    def encode(self) -> bytes:
        return struct.pack('<10h', *astuple(self))


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

    def encode(self) -> bytes:
        return struct.pack('<h8i', *astuple(self))


@dataclass
class Interactable:
    id: int
    x_pos: int
    z_pos: int
    x_size: int
    z_size: int

    def encode(self) -> bytes:
        return struct.pack('<5h', *astuple(self))


@dataclass
class RoomLayout:
    address: int = 0
    colliders: list[Collider] = field(default_factory=list)
    rectangle_colliders: list[RectangleCollider] = field(default_factory=list)
    triangle_colliders: list[TriangleCollider] = field(default_factory=list)
    circle_colliders: list[CircleCollider] = field(default_factory=list)
    cameras: list[Camera] = field(default_factory=list)
    cuts: list[CameraCut] = field(default_factory=list)
    interactables: list[Interactable] = field(default_factory=list)


class Undefined:
    def __abs__(self) -> Undefined:
        return self

    def __add__(self, other: Any) -> Undefined:
        return self

    def __radd__(self, other: Any) -> Undefined:
        return self

    def __sub__(self, other: Any) -> Undefined:
        return self

    def __rsub__(self, other: Any) -> Undefined:
        return self

    def __mul__(self, other: Any) -> Undefined:
        return self

    def __rmul__(self, other: Any) -> Undefined:
        return self

    def __truediv__(self, other: Any) -> Undefined:
        return self

    def __rtruediv__(self, other: Any) -> Undefined:
        return self

    def __floordiv__(self, other: Any) -> Undefined:
        return self

    def __rfloordiv__(self, other: Any) -> Undefined:
        return self

    def __neg__(self) -> Undefined:
        return self

    def __pos__(self) -> Undefined:
        return self

    def __and__(self, other: Any) -> Undefined:
        return self

    def __rand__(self, other: Any) -> Undefined:
        return self

    def __or__(self, other: Any) -> Undefined:
        return self

    def __ror__(self, other: Any) -> Undefined:
        return self

    def __xor__(self, other: Any) -> Undefined:
        return self

    def __rxor__(self, other: Any) -> Undefined:
        return self

    def __eq__(self, other: Any) -> bool:
        return False

    def __ne__(self, other: Any) -> bool:
        return False


UNDEFINED = Undefined()


@dataclass
class Register:
    value: int | Undefined = field(default_factory=lambda: UNDEFINED)
    source: int | Undefined = field(default_factory=lambda: UNDEFINED)
    instruction: int | Undefined = field(default_factory=lambda: UNDEFINED)


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
    MAX_COLLIDERS = 100
    MAX_ENTRANCES = 15
    MAX_INTERACTABLES = 50
    MAX_ITEM_ID = 38
    MAX_ROOMS_PER_MAP = 21
    MIN_ADDRESS = 0x80000000
    NAME_REGEX = re.compile(rb'[ABCD]\d{2}[0-9A-Z]{2}')
    ROOM_LAYOUT_SIZE = 0x2d5c
    TRIGGER_SIZE = 16

    ROOM_RECT_OFFSET = 0x4b4
    ROOM_TRI_OFFSET = 0xc84
    ROOM_CIRCLE_OFFSET = 0x15e4
    ROOM_CAMERA_OFFSET = 0x1a94
    ROOM_CUT_OFFSET = 0x1b60
    ROOM_INTERACT_OFFSET = 0x2970

    def __init__(self, module_id: int, layout: RoomLayout, backgrounds: list[BackgroundSet],
                 actor_layouts: list[ActorLayoutSet], triggers: TriggerSet, entrances: list[EntranceSet],
                 load_address: int, raw_data: bytes, functions: dict[int, CallbackFunction]):
        self.module_id = module_id
        self.layout = layout
        self.backgrounds = backgrounds
        self.actor_layouts = actor_layouts
        self.triggers = triggers
        self.entrances = entrances
        self.load_address = load_address
        self.raw_data = raw_data
        self.functions = functions

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

    def write(self, f: BinaryIO, *, language: str = None, **kwargs):
        self.validate_for_write()

        f.write(self.raw_data)

        f.seek(0)
        f.write(self.module_id.to_bytes(4, 'little'))

        if self.layout.address > 0:
            f.seek(self.layout.address)

            f.write(len(self.layout.colliders).to_bytes(4, 'little'))
            for collider in self.layout.colliders:
                f.write(collider.encode())

            f.seek(self.layout.address + self.ROOM_RECT_OFFSET)
            for rect in self.layout.rectangle_colliders:
                f.write(rect.encode())

            f.seek(self.layout.address + self.ROOM_TRI_OFFSET)
            for tri in self.layout.triangle_colliders:
                f.write(tri.encode())

            f.seek(self.layout.address + self.ROOM_CIRCLE_OFFSET)
            for circle in self.layout.circle_colliders:
                f.write(circle.encode())

            f.seek(self.layout.address + self.ROOM_CAMERA_OFFSET)
            f.write(len(self.layout.cameras).to_bytes(4, 'little'))
            for camera in self.layout.cameras:
                f.write(camera.encode())

            f.seek(self.layout.address + self.ROOM_CUT_OFFSET)
            for cut in self.layout.cuts:
                f.write(b'\0\0')  # marker
                f.write(cut.encode())
            f.write(b'\xff\xff')  # end marker

            f.seek(self.layout.address + self.ROOM_INTERACT_OFFSET)
            f.write(len(self.layout.interactables).to_bytes(4, 'little'))
            for interactable in self.layout.interactables:
                f.write(interactable.encode())

        for layout_set in self.actor_layouts:
            if layout_set.address > 0:
                f.seek(layout_set.address)
                f.write(layout_set.encode())

        for background_set in self.backgrounds:
            if background_set.address > 0:
                f.seek(background_set.address)
                f.write(background_set.encode())

                for background in background_set.backgrounds:
                    mask_offset = background.mask_address - self.load_address
                    if mask_offset > 0:
                        f.seek(mask_offset)
                        for mask in background.masks:
                            f.write(mask.encode())

        for entrance_set in self.entrances:
            if entrance_set.address > 0:
                f.seek(entrance_set.address)
                f.write(entrance_set.encode())

        if self.triggers.address > 0:
            f.seek(self.triggers.address)
            f.write(self.triggers.encode())

        addresses = None
        if language is not None:
            addresses = REGION_ADDRESSES[language]
        for address, callback in self.functions.items():
            for call in callback.calls:
                offset = call.call_address - self.load_address
                f.seek(offset)
                if call.is_enabled and addresses is not None:
                    dest_address = addresses[call.name]
                    # jal dest_address
                    instruction = 0x0c000000 | ((dest_address & 0x3ffffff) >> 2)
                    f.write(instruction.to_bytes(4, 'little'))
                elif call.is_enabled is False:
                    f.write(b'\0\0\0\0')  # nop

                argument_types = KNOWN_FUNCTIONS[call.name].arguments
                for arg_type, (inst_addr, value) in zip(argument_types, call.arguments):
                    if arg_type == ArgumentType.GAME_STATE:
                        continue
                    self.update_immediate(inst_addr, value, f)

            self.update_immediate(callback.return_value_instruction, callback.return_value, f)

    def update_immediate(self, inst_addr: int | None, value: int | None, f: BinaryIO):
        if inst_addr is None or value is None:
            return

        offset = inst_addr - self.load_address
        raw_word = self.raw_data[offset:offset + 4]
        word = int.from_bytes(raw_word, 'little')
        instruction = rabbitizer.Instruction(word, inst_addr)
        # we only support immediate loads
        # TODO: flag these arguments so the UI won't let the user try to change them
        opcode = instruction.getOpcodeName()
        if instruction.rs != rabbitizer.RegGprO32.zero or not (opcode == 'addiu' or
                                                               (opcode == 'addu'
                                                                and instruction.rt == rabbitizer.RegGprO32.zero)):
            print(f'Warning: could not update {instruction} at {inst_addr:08X}')
            return
        if value > 0xffff:
            raise ValueError(f'Value {value} is too large to encode as an immediate')
        target_reg = (instruction.rd if opcode == 'addu' else instruction.rt).value
        if value == 0:
            # addu target,$zero,$zero
            new_inst = (target_reg << 11) | 0x00000021
        else:
            # addiu target,$zero,imm
            new_inst = 0x24000000 | (target_reg << 16) | value
        f.seek(offset)
        f.write(new_inst.to_bytes(4, 'little'))

    def validate_for_write(self):
        if len(self.layout.colliders) > self.MAX_COLLIDERS:
            raise ValueError(f'Too many colliders: max {self.MAX_COLLIDERS}, found {len(self.layout.colliders)}')
        if len(self.layout.rectangle_colliders) > self.MAX_COLLIDERS:
            raise ValueError(f'Too many rectangle colliders: max {self.MAX_COLLIDERS}, '
                             f'found {len(self.layout.rectangle_colliders)}')
        if len(self.layout.triangle_colliders) > self.MAX_COLLIDERS:
            raise ValueError(f'Too many triangle colliders: max {self.MAX_COLLIDERS}, '
                             f'found {len(self.layout.triangle_colliders)}')
        if len(self.layout.circle_colliders) > self.MAX_COLLIDERS:
            raise ValueError(f'Too many circle colliders: max {self.MAX_COLLIDERS}, '
                             f'found {len(self.layout.circle_colliders)}')

        if len(self.layout.cameras) > self.MAX_CAMERAS:
            raise ValueError(f'Too many cameras: max {self.MAX_CAMERAS}, found {len(self.layout.cameras)}')

        if len(self.layout.interactables) > self.MAX_INTERACTABLES:
            raise ValueError(f'Too many interactables: max {self.MAX_INTERACTABLES}, '
                             f'found {len(self.layout.interactables)}')

        for i, actor_layout_set in enumerate(self.actor_layouts):
            for j, actor_layout in enumerate(actor_layout_set.layouts):
                if len(actor_layout.actors) != self.MAX_ACTORS:
                    raise ValueError(f'Wrong number of actors in layout set {i} layout {j}: expected {self.MAX_ACTORS},'
                                     f' found {len(actor_layout.actors)}')

    def save_metadata(self, f: TextIO):
        json.dump({
            'loadAddress': self.load_address,
            'actorLayouts': [layout_set.address + self.load_address for layout_set in self.actor_layouts],
            'roomLayout': self.layout.address + self.load_address,
            'backgrounds': [background_set.address + self.load_address for background_set in self.backgrounds],
            'triggers': self.triggers.address + self.load_address,
            'entrances': [entrance_set.address + self.load_address for entrance_set in self.entrances],
            'numEntrances': len(self.entrances[0].entrances) if self.entrances else 0,
            'functions': {f'{addr:08X}': asdict(callback) for addr, callback in self.functions.items()},
        }, f)

    @classmethod
    def load_with_metadata(cls, path: Path, language: str = None) -> RoomModule:
        meta_path = path.with_suffix('.json')
        with meta_path.open() as f:
            metadata = json.load(f)

        load_address = metadata['loadAddress']
        metadata_functions = metadata.get('functions')
        if metadata_functions is None:
            functions = None
        else:
            functions = {}
            for hex_addr, callback in metadata.get('functions', {}).items():
                functions[int(hex_addr, 16)] = CallbackFunction([FunctionCall(**call) for call in callback['calls']],
                                                                callback['return_value_instruction'],
                                                                callback['return_value'])

        if language is not None:
            addresses = REGION_ADDRESSES[language]
            game_state = addresses['GameState']

            known_functions = {}
            for name in KNOWN_FUNCTIONS:
                if name in addresses:
                    known_functions[addresses[name]] = name
        else:
            game_state = 0
            known_functions = None

        room_addresses = RoomAddresses(game_state, 0, set(metadata['actorLayouts']), {metadata['triggers']},
                                       set(metadata['backgrounds']), {metadata['roomLayout']},
                                       set(metadata['entrances']), metadata['numEntrances'])

        data = path.read_bytes()
        return cls.parse_with_addresses(data, load_address, room_addresses, functions, known_functions)

    @classmethod
    def _is_ptr(cls, p: int) -> bool:
        return p == 0 or cls.MIN_ADDRESS <= p <= cls.MAX_ADDRESS

    @classmethod
    def parse_entrances(cls, data: bytes, address: int, num_entrances: int, addresses: RoomAddresses) -> EntranceSet:
        entrance_set = EntranceSet(address)
        if num_entrances > 0:
            for _ in range(num_entrances):
                entrance_set.entrances.append(Entrance(*struct.unpack_from('<4hi', data, address)))
                address += 12
        else:
            # try to find the end heuristically
            for _ in range(cls.MAX_ENTRANCES):
                if (address in addresses.backgrounds or address in addresses.actor_layouts
                        or address in addresses.room_layout or address in addresses.triggers):
                    break  # if we've run into one of the other data structures, we're at the end
                entrance = Entrance(*struct.unpack_from('<4hi', data, address))
                if not -1 <= entrance.room_index <= cls.MAX_ROOMS_PER_MAP:
                    break  # invalid room index
                if entrance.room_index == entrance.x == entrance.y == entrance.z == entrance.angle == 0:
                    break  # all zeroes
                if not -0x1000 <= entrance.angle <= 0x1000:
                    break  # invalid angle
                entrance_set.entrances.append(entrance)
                address += 12
            else:
                # MAX_ENTRANCES is set a little higher than the actual max number of entrances any of the rooms have,
                # so if we don't hit one of our exit conditions, we probably went too far
                return EntranceSet(address)
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
        collider_count = int.from_bytes(data[address:address + 4], 'little')
        if collider_count > cls.MAX_COLLIDERS or (collider_count == 0 and not known_good):
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

        if num_rects > cls.MAX_COLLIDERS or num_tris > cls.MAX_COLLIDERS or num_circles > cls.MAX_COLLIDERS:
            raise ValueError('Too many collider shapes')

        # these are fixed-size arrays (size = MAX_REGIONS), which is why we manually calculate the offset after
        # reading the elements that are actually present
        offset = address + cls.ROOM_RECT_OFFSET
        for _ in range(num_rects):
            room_layout.rectangle_colliders.append(RectangleCollider(*struct.unpack_from('<5i', data, offset)))
            offset += 20

        offset = address + cls.ROOM_TRI_OFFSET
        for _ in range(num_tris):
            room_layout.triangle_colliders.append(TriangleCollider(*struct.unpack_from('<6i', data, offset)))
            offset += 24

        offset = address + cls.ROOM_CIRCLE_OFFSET
        for _ in range(num_circles):
            room_layout.circle_colliders.append(CircleCollider(*struct.unpack_from('<3i', data, offset)))
            offset += 12

        offset = address + cls.ROOM_CAMERA_OFFSET
        num_cameras = int.from_bytes(data[offset:offset + 4], 'little')
        if num_cameras > cls.MAX_CAMERAS or (num_cameras == 0 and not known_good):
            raise ValueError('Invalid number of cameras')

        offset += 4
        for _ in range(num_cameras):
            room_layout.cameras.append(Camera(*struct.unpack_from('<10h', data, offset)))
            offset += 20

        offset = address + cls.ROOM_CUT_OFFSET
        while True:
            marker = int.from_bytes(data[offset:offset + 2], 'little', signed=True)
            if marker < 0:
                break

            room_layout.cuts.append(CameraCut(*struct.unpack_from('<h8i', data, offset + 2)))
            offset += 0x24

        offset = address + cls.ROOM_INTERACT_OFFSET
        num_interactables = int.from_bytes(data[offset:offset + 4], 'little')
        if num_interactables > cls.MAX_COLLIDERS:
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
    def parse_function(cls, data: bytes, start_address: int, module_space: range, regs: list[Register],
                       room_address: RoomAddresses, known_functions: dict[int, str] = None,
                       function_calls: list[FunctionCall] = None) -> tuple[int | None, int | None]:
        in_delay_slot = False
        jump_address = None
        do_return = False
        restore_regs = False
        grab_room_layout_ptr = False
        found_entrance_array = False
        ever_branched = False
        function_name = None
        arg_regs = [rabbitizer.RegGprO32.a0.value, rabbitizer.RegGprO32.a1.value, rabbitizer.RegGprO32.a2.value,
                    rabbitizer.RegGprO32.a3.value]
        if known_functions is None:
            known_functions = {}

        for i in range(start_address, module_space.stop, 4):
            offset = i - module_space.start
            word = int.from_bytes(data[offset:offset+4], 'little')
            inst = rabbitizer.Instruction(word, i)
            if not inst.isValid():
                raise ValueError(f'Invalid instruction at address {i:08X}')

            match inst.getOpcodeName():
                case 'lui':
                    reg = regs[inst.rt.value]
                    reg.value = inst.getProcessedImmediate() << 16
                    reg.source = UNDEFINED
                    reg.instruction = i
                case 'addiu':
                    reg = regs[inst.rt.value]
                    reg.value = regs[inst.rs.value].value + inst.getProcessedImmediate()
                    reg.source = UNDEFINED
                    reg.instruction = i
                case 'addu':
                    reg = regs[inst.rd.value]
                    reg.value = regs[inst.rs.value].value + regs[inst.rt.value].value
                    reg.source = UNDEFINED
                    reg.instruction = i
                case 'jal':
                    ever_branched = True
                    dest = inst.getInstrIndexAsVram()
                    in_delay_slot = True
                    # when we're tracking function calls, we don't want to step into them, just record the interesting
                    # ones
                    if function_calls is None:
                        if dest in module_space:
                            jump_address = dest
                        elif dest == room_address.set_room_layout:
                            grab_room_layout_ptr = True
                    elif dest in known_functions:
                        function_name = known_functions[dest]
                        # we can't grab the args yet because they could be set in the delay slot
                    continue
                case 'jr':
                    in_delay_slot = True
                    do_return = inst.isJrRa()
                    continue
                case 'sw':
                    address = regs[inst.rs.value].value + inst.getProcessedImmediate()
                    value_reg = regs[inst.rt.value]
                    value = value_reg.value
                    if address is not UNDEFINED and value is not UNDEFINED:
                        if value in module_space:
                            room_address.set_by_address(address, value)
                            if room_address.is_complete:
                                return None, None  # nothing left to do
                        if (function_calls is not None
                                and address == room_address.game_state + GameStateOffsets.MESSAGE_ID
                                and value_reg.instruction is not UNDEFINED):
                            # we'll treat this as a fake call to SetMessageId, because frequently the game just sets
                            # the message ID directly instead of calling the function. we set is_enabled to None because
                            # this isn't a real function call and can't be enabled or disabled
                            instruction = value_reg.instruction
                            call = FunctionCall(i, 'SetMessageId', [(instruction, value)], None)
                            if call not in function_calls:
                                function_calls.append(call)
                case 'lw':
                    address = regs[inst.rs.value].value + inst.getProcessedImmediate()
                    if address is not UNDEFINED:
                        reg = regs[inst.rt.value]
                        reg.value = room_address.get_by_address(address)
                        reg.source = address
                        reg.instruction = i
                case 'lh':
                    address = regs[inst.rs.value].value + inst.getProcessedImmediate()
                    if address is not UNDEFINED:
                        reg = regs[inst.rt.value]
                        reg.value = room_address.get_by_address(address) & 0xffff
                        reg.source = address
                        reg.instruction = i
                case _:
                    if (is_branch := inst.isBranch()) and inst.readsRt() and inst.readsRs():
                        # first, check if we're comparing to the game state's lastRoom field; that will identify if this
                        # value came from the room's entrance array
                        had_found_entrance_array = found_entrance_array
                        if (room_address.is_last_room_address(regs[inst.rt.value].source)
                                and regs[inst.rs.value].source is not UNDEFINED):
                            room_address.entrances.add(regs[inst.rs.value].source)
                            found_entrance_array = True
                        elif (room_address.is_last_room_address(regs[inst.rs.value].source)
                              and regs[inst.rt.value].source is not UNDEFINED):
                            room_address.entrances.add(regs[inst.rt.value].source)
                            found_entrance_array = True

                        # for some reason, this function can return a signed number, so do the two's complement
                        dest = (inst.getBranchVramGeneric() + (1 << 32)) & 0xffffffff
                        if had_found_entrance_array != found_entrance_array:
                            # if we just found the entrance array, try to follow the branch and see if it leads us to
                            # the condition checking the count
                            room_address.num_entrances = cls.find_entrance_count(data, dest, module_space)

                    if is_branch or inst.isJump():
                        ever_branched = True
                        # for some reason, this function can return a signed number, so do the two's complement
                        dest = (inst.getBranchVramGeneric() + (1 << 32)) & 0xffffffff

                        # we only care about forward branches because we don't want to revisit code we've already seen
                        if dest > i:
                            in_delay_slot = True
                            jump_address = dest
                            restore_regs = True
                            do_return = inst.isUnconditionalBranch()
                            continue
                        if inst.isUnconditionalBranch():
                            # if we encounter an unconditional branch, exit this code path
                            in_delay_slot = True
                            do_return = True
                            continue

                    # wipe out any registers modified by instructions we don't know about
                    if inst.modifiesRt():
                        reg = regs[inst.rt.value]
                        reg.value = UNDEFINED
                        reg.source = UNDEFINED
                        reg.instruction = UNDEFINED
                    if inst.modifiesRd():
                        reg = regs[inst.rd.value]
                        reg.value = UNDEFINED
                        reg.source = UNDEFINED
                        reg.instruction = UNDEFINED
                    if inst.modifiesRs():
                        reg = regs[inst.rs.value]
                        reg.value = UNDEFINED
                        reg.source = UNDEFINED
                        reg.instruction = UNDEFINED

            if in_delay_slot:
                in_delay_slot = False

                if function_name is not None:
                    needed_args = KNOWN_FUNCTIONS[function_name].arguments
                    arg_values = []
                    for arg_index, arg_type in enumerate(needed_args):
                        reg_index = arg_regs[arg_index]
                        reg = regs[reg_index]
                        value = reg.value
                        instruction = reg.instruction
                        # we don't care about the game state argument because it's always the same, so if that one is
                        # undefined, it's fine
                        if (value is UNDEFINED or instruction is UNDEFINED) and arg_type != ArgumentType.GAME_STATE:
                            break
                        if value is UNDEFINED:
                            value = None
                        if instruction is UNDEFINED:
                            instruction = None
                        arg_values.append((instruction, value))
                    else:
                        # we didn't find any invalid arguments
                        call = FunctionCall(i - 4, function_name, arg_values)
                        if call not in function_calls:
                            function_calls.append(call)
                    function_name = None

                if grab_room_layout_ptr:
                    room_layout_ptr = regs[rabbitizer.RegGprO32.a2.value].value
                    if room_layout_ptr is not UNDEFINED and room_layout_ptr in module_space:
                        room_address.room_layout.add(room_layout_ptr)
                    else:
                        raise ValueError('Found call to SetRoomLayout but a2 was undefined')
                    if room_address.is_complete:
                        return None, None  # nothing left to do

                if jump_address is not None:
                    regs_to_restore = [replace(reg) for reg in regs]
                    cls.parse_function(data, jump_address, module_space, regs, room_address, known_functions,
                                       function_calls)
                    if room_address.is_complete:
                        # we've found everything we were looking for; no need to keep parsing
                        return None, None

                    jump_address = None
                    if restore_regs:
                        regs = regs_to_restore
                        restore_regs = False
                elif not do_return:
                    # clobber registers
                    for j in range(1, len(regs)):
                        if not rabbitizer.RegGprO32.s0.value <= j <= rabbitizer.RegGprO32.s7.value:
                            reg = regs[j]
                            reg.value = UNDEFINED
                            reg.source = UNDEFINED
                            reg.instruction = UNDEFINED

                if do_return:
                    # we don't do this logic in any of the other returns because those are all handling filling out the
                    # room addresses, and we only care about the return value when we're tracing function calls
                    return_value_instruction = None
                    return_value = None
                    # if we ever branched, then we don't have a way to keep track of whether any return value we ended
                    # up with varied by branch, so we exclude those. we only track a hard-coded return value when there
                    # was only one path through the code meaning it was the only return value we could've gotten.
                    if not ever_branched:
                        reg = regs[rabbitizer.RegGprO32.v0.value]
                        if reg.instruction is not UNDEFINED and reg.value is not UNDEFINED:
                            return_value_instruction = reg.instruction
                            return_value = reg.value
                    return return_value_instruction, return_value

    @classmethod
    def parse_with_addresses(cls, data: bytes, load_address: int, room_addresses: RoomAddresses,
                             functions: dict[int, CallbackFunction] = None,
                             known_functions: dict[int, str] = None) -> RoomModule:
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

        entrance_sets = []
        for address in room_addresses.entrances:
            offset = address - load_address
            entrance_sets.append(cls.parse_entrances(data, offset, room_addresses.num_entrances, room_addresses))

        if functions is None:
            functions = {}
            for trigger in triggers.triggers:
                if trigger.enabled_callback != 0:
                    functions[trigger.enabled_callback] = CallbackFunction([], None, None)
                if trigger.trigger_callback != 0:
                    functions[trigger.trigger_callback] = CallbackFunction([], None, None)

            if known_functions is not None:
                for address, function in functions.items():
                    regs = [Register() for _ in range(32)]
                    regs[0].value = 0
                    regs[rabbitizer.RegGprO32.a0.value].value = room_addresses.game_state
                    rvi, rv = cls.parse_function(data, address, range(load_address, load_address + len(data)), regs,
                                                 room_addresses, known_functions, function.calls)
                    function.return_value_instruction = rvi
                    function.return_value = rv

        return cls(module_id, room_layout, backgrounds, actor_layouts, triggers, entrance_sets, load_address, data,
                   functions)

    @classmethod
    def parse(cls, f: BinaryIO, language: str, entry_point: int) -> RoomModule:
        data = f.read()
        module_id = int.from_bytes(data[:4], 'little')

        addresses = REGION_ADDRESSES[language]
        load_address = addresses['ModuleLoadAddresses'][0]

        if (entry_point - load_address) >= len(data):
            # this is a stub; return a dummy module
            return cls(module_id, RoomLayout(), [], [], TriggerSet(), [], load_address,
                       data, {})

        game_state = addresses['GameState']
        regs = [Register() for _ in range(32)]
        regs[0].value = 0
        regs[rabbitizer.RegGprO32.a0.value].value = game_state
        room_addresses = RoomAddresses(game_state, addresses['SetRoomLayout'])
        cls.parse_function(data, entry_point, range(load_address, load_address + len(data)), regs, room_addresses)
        if not room_addresses.is_valid:
            raise ValueError('Failed to parse room structure')

        known_functions = {}
        for name in KNOWN_FUNCTIONS:
            if name in addresses:
                known_functions[addresses[name]] = name

        return cls.parse_with_addresses(data, load_address, room_addresses, known_functions=known_functions)

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

        return cls(module_id, room_layout, [backgrounds], actor_layouts, triggers, [], load_address,
                   data, {})


def dump_info(module_path: str, language: str | None, force: bool, json_path: str | None, entry_point: int = None):
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

    if json_path is not None:
        with open(json_path, 'w') as f:
            module.save_metadata(f)

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

    print('Entrance sets')
    for i, entrance_set in enumerate(module.entrances):
        print(f'\tEntrance set {i}: {entrance_set.address:08X}')
        for j, entrance in enumerate(entrance_set.entrances):
            print(f'\t\tEntrance {j}')
            print(f'\t\t\tRoom index: {entrance.room_index}')
            print(f'\t\t\tX: {entrance.x}')
            print(f'\t\t\tY: {entrance.y}')
            print(f'\t\t\tZ: {entrance.z}')
            print(f'\t\t\tAngle: {entrance.angle}')

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
    parser.add_argument('-j', '--json', help="Write module metadata to the given JSON file. The file won't be written "
                        "if the module isn't valid unless the --force flag was given.")
    parser.add_argument('module', help='Path to the room module to examine')

    args = parser.parse_args()
    dump_info(args.module, args.language, args.force, args.json, args.entry)
