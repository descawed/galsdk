from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from enum import IntEnum, IntFlag
from typing import BinaryIO


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
    layouts: list[ActorLayout] = field(default_factory=lambda: [])


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
    triggers: list[Trigger] = field(default_factory=lambda: [])


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
    backgrounds: list[Background] = field(default_factory=lambda: [])


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


class RoomModule:
    ACTOR_INSTANCE_SIZE = 16
    ACTOR_LAYOUT_SIZE = 100
    LOAD_ADDRESS = 0x801EC628
    MAX_ACTORS = 4
    MAX_ADDRESS = 0x801FFFFF
    MAX_CAMERAS = 10
    MAX_ITEM_ID = 38
    MAX_REGIONS = 100
    MIN_ADDRESS = 0x80000000
    NAME_REGEX = re.compile(rb'[ABCD]\d{4}')
    ROOM_LAYOUT_SIZE = 0x2d5c
    TRIGGER_SIZE = 16

    def __init__(self, room_id: int, layout: RoomLayout, backgrounds: BackgroundSet, actor_layouts: ActorLayoutSet,
                 triggers: TriggerSet):
        self.room_id = room_id
        self.layout = layout
        self.backgrounds = backgrounds
        self.actor_layouts = actor_layouts
        self.triggers = triggers

    @property
    def is_valid(self) -> bool:
        return len(self.actor_layouts.layouts) > 0 and len(self.backgrounds.backgrounds) > 0 and \
               len(self.layout.cameras) > 0

    @property
    def name(self) -> str | None:
        try:
            return self.actor_layouts.layouts[0].name
        except IndexError:
            return None

    @classmethod
    def _is_ptr(cls, p: int) -> bool:
        return p == 0 or cls.MIN_ADDRESS <= p <= cls.MAX_ADDRESS

    @classmethod
    def load(cls, f: BinaryIO) -> RoomModule:
        data = f.read()
        room_id = int.from_bytes(data[:4], 'little')

        # the rest of the module is just a binary blob, so we have to heuristically search for the data structures we're
        # interested in
        # start by recording which addresses are used by other stuff
        used_addresses = [range(4)]

        # look for the actor layouts, which can be identified by regex
        actor_layouts = ActorLayoutSet()
        for match in cls.NAME_REGEX.finditer(data):
            address = match.start()
            if actor_layouts.address == 0:
                actor_layouts.address = address
            if (address - actor_layouts.address) % cls.ACTOR_LAYOUT_SIZE != 0:
                # doesn't line up in layout array; ignore it
                continue

            layout_data = data[address:address + cls.ACTOR_LAYOUT_SIZE]
            name = layout_data[:6].rstrip(b'\0').decode()
            unknown = layout_data[6:0x24]
            instances = []
            for i in range(cls.MAX_ACTORS):
                start = 0x24 + i * cls.ACTOR_INSTANCE_SIZE
                instances.append(ActorInstance(*struct.unpack_from('H4h3H', layout_data, start)))
            actor_layouts.layouts.append(ActorLayout(name, unknown, instances))
        if actor_layouts.address > 0:
            used_addresses.append(range(actor_layouts.address,
                                        actor_layouts.address + len(actor_layouts.layouts) * cls.ACTOR_LAYOUT_SIZE))

        # next, look for room layout. we'll assume it's aligned on a 4-byte boundary
        max_colliders = cls.MAX_REGIONS * 3  # rectangle (includes wall), triangle, circle
        room_layout = RoomLayout()
        for i in range(0, len(data), 4):
            if any(i in region for region in used_addresses):
                continue

            collider_count = int.from_bytes(data[i:i+4], 'little')
            if collider_count == 0 or collider_count > max_colliders:
                # invalid number of colliders; this isn't it
                continue

            # reset the room layout from any previous aborted parsing attempt
            room_layout = RoomLayout()

            offset = i + 4
            num_rects = num_tris = num_circles = 0
            try:
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
                    unknown = int.from_bytes(data[offset + 8:offset + 12], 'little')
                    room_layout.colliders.append(Collider(collider_type, element_ptr, unknown))
                    offset += 12
            except ValueError:
                # we got an invalid collider; this isn't it
                continue

            if num_rects > cls.MAX_REGIONS or num_tris > cls.MAX_REGIONS or num_circles > cls.MAX_REGIONS:
                continue

            try:
                # these are fixed-size arrays (size = MAX_REGIONS), which is why we manually calculate the offset after
                # reading the elements that are actually present
                offset = i + 0x4b4
                for _ in range(num_rects):
                    room_layout.rectangle_colliders.append(RectangleCollider(*struct.unpack_from('5i', data, offset)))
                    offset += 20

                offset = i + 0xc84
                for _ in range(num_tris):
                    room_layout.triangle_colliders.append(TriangleCollider(*struct.unpack_from('6i', data, offset)))
                    offset += 24

                offset = i + 0x15e4
                for _ in range(num_circles):
                    room_layout.circle_colliders.append(CircleCollider(*struct.unpack_from('3i', data, offset)))
                    offset += 12

                offset = i + 0x1a94
                num_cameras = int.from_bytes(data[offset:offset + 4], 'little')
                if num_cameras == 0 or num_cameras > cls.MAX_CAMERAS:
                    continue

                offset += 4
                for _ in range(num_cameras):
                    room_layout.cameras.append(Camera(*struct.unpack_from('10h', data, offset)))
                    offset += 20

                offset = i + 0x1b60
                while True:
                    marker = int.from_bytes(data[offset:offset + 2], 'little', signed=True)
                    if marker < 0:
                        break

                    room_layout.cuts.append(CameraCut(*struct.unpack_from('h8i', data, offset + 4)))
                    offset += 0x24

                offset = i + 0x2970
                num_interactables = int.from_bytes(data[offset:offset + 4], 'little')
                if num_interactables > cls.MAX_REGIONS:
                    continue

                offset += 4
                for _ in range(num_interactables):
                    room_layout.interactables.append(Interactable(*struct.unpack_from('5h', data, offset)))
                    offset += 10
            except struct.error:
                # parse error; this isn't the struct we're looking for
                continue

            room_layout.address = i
            break

        if room_layout.address > 0:
            used_addresses.append(range(room_layout.address, room_layout.address + cls.ROOM_LAYOUT_SIZE))

        # next, look for trigger callbacks
        triggers = TriggerSet()
        num_triggers = len(room_layout.interactables)
        if num_triggers > 0:
            for i in range(0, len(data), 4):
                if any(i in region for region in used_addresses):
                    continue

                # reset the triggers from any previous failed parse attempt
                triggers = TriggerSet()
                offset = i
                try:
                    for _ in range(num_triggers):
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
                        offset += cls.TRIGGER_SIZE
                except (IndexError, ValueError):
                    continue

                triggers.address = i
                break

        if triggers.address > 0:
            used_addresses.append(range(triggers.address, triggers.address + num_triggers * cls.TRIGGER_SIZE))

        # finally, look for background image definitions
        backgrounds = BackgroundSet()
        num_backgrounds = len(room_layout.cameras)
        if num_backgrounds > 0:
            for i in range(0, len(data), 4):
                if any(i in region for region in used_addresses):
                    continue

                # reset the backgrounds from any previous failed parse attempt
                backgrounds = BackgroundSet()
                offset = i
                try:
                    for _ in range(num_backgrounds):
                        index = int.from_bytes(data[offset:offset + 2], 'little')
                        num_masks = int.from_bytes(data[offset + 2:offset + 4], 'little')
                        mask_ptr = int.from_bytes(data[offset + 4:offset + 8], 'little')

                        # find masks
                        mask_offset = mask_ptr - cls.LOAD_ADDRESS
                        if mask_offset < 0 or mask_offset >= len(data):
                            raise ValueError
                        background = Background(index, mask_ptr, [])
                        for _ in range(num_masks):
                            background.masks.append(BackgroundMask(*struct.unpack_from('2I4h', data, mask_offset)))
                            mask_offset += 16

                        backgrounds.backgrounds.append(background)
                        offset += 8
                except (IndexError, ValueError, struct.error):
                    continue

                backgrounds.address = i
                break

        return cls(room_id, room_layout, backgrounds, actor_layouts, triggers)
