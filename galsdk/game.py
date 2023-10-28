from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum, auto
from typing import Self

from psx import Region


class Stage(str, Enum):
    A = 'A'
    B = 'B'
    C = 'C'
    D = 'D'

    def __str__(self):
        return self.value

    def __int__(self) -> int:
        return list(type(self)).index(self)

    @classmethod
    def from_int(cls, int_index: int) -> Self:
        return list(cls)[int_index]


class GameStateOffsets(IntEnum):
    LAST_ROOM = 0xE
    BACKGROUNDS = 0x18
    ACTOR_LAYOUTS = 0x2C
    TRIGGERS = 0x30
    MESSAGE_ID = 0x44


KEY_ITEM_NAMES = [
    'Unused #0',
    'Security Card',
    'Beeject',
    'Freezer Room Key',
    'PPEC Storage Key',
    'Fuse',
    'Liquid Explosive',
    'Unused #7',
    'Security Card (reformatted)',
    'Special PPEC Office Key',
    'Unused #10',
    'Test Lab Key',
    'Control Room Key',
    'Research Lab Key',
    'Two-Headed Snake',
    'Two-Headed Monkey',
    'Two-Headed Wolf',
    'Two-Headed Eagle',
    'Unused #18',
    'Backdoor Key',
    'Door Knob',
    '9 Ball',
    "Mother's Ring",
    "Father's Ring",
    "Lilia's Doll",
    'Metamorphosis',
    'Bedroom Key',
    'Second Floor Key',
    'Medical Staff Notes',
    'G Project Report',
    'Photo of Parents',
    "Rion's test data",
    "Dr. Lem's Notes",
    'New Replicative Computer Theory',
    "Dr. Pascalle's Diary",
    'Letter from Elsa',
    'Newspaper',
    '3 Ball',
    'Shed Key',
    'Letter from Lilia',
]
MED_ITEM_NAMES = [
    'Nalcon',
    'Red',
    'D-Felon',
    'Recovery Capsule',
    'Delmetor',
    'Appollinar',
    'Skip',
]
MAP_NAMES = [
    'Hospital 15F',
    'Hospital 14F',
    'Hospital 13F',
    'Your House 1F',
    'Your House 2F',
    'Hotel 1F',
    'Hotel 2F',
    'Hotel 3F',
    'Mushroom Tower',
]
NUM_KEY_ITEMS = len(KEY_ITEM_NAMES)
NUM_MED_ITEMS = len(MED_ITEM_NAMES)
NUM_MAPS = len(MAP_NAMES)
NUM_MOVIES = 65
MODULE_ENTRY_SIZE = 8


class ArgumentType(Enum):
    INTEGER = auto()
    KEY_ITEM = auto()
    MESSAGE = auto()
    MAP = auto()
    ROOM = auto()
    STAGE = auto()
    MED_ITEM = auto()
    GAME_STATE = auto()
    MOVIE = auto()


@dataclass
class Function:
    arguments: list[ArgumentType]
    returns_value: bool = False


KNOWN_FUNCTIONS = {
    'GetStateFlag': Function([
        ArgumentType.GAME_STATE,
        ArgumentType.INTEGER,
    ], True),
    'SetStateFlag': Function([
        ArgumentType.GAME_STATE,
        ArgumentType.INTEGER,
    ]),
    'ClearStateFlag': Function([
        ArgumentType.GAME_STATE,
        ArgumentType.INTEGER,
    ]),
    'GetStageStateFlag': Function([
        ArgumentType.GAME_STATE,
        ArgumentType.INTEGER,
        ArgumentType.STAGE,
    ], True),
    'SetStageStateFlag': Function([
        ArgumentType.GAME_STATE,
        ArgumentType.INTEGER,
        ArgumentType.STAGE,
    ]),
    'ClearStageStateFlag': Function([
        ArgumentType.GAME_STATE,
        ArgumentType.INTEGER,
        ArgumentType.STAGE,
    ]),
    'PickUpFile': Function([
        ArgumentType.INTEGER,
        ArgumentType.KEY_ITEM,
    ]),
    'PickUpKeyItem': Function([
        ArgumentType.GAME_STATE,
        ArgumentType.KEY_ITEM,
        ArgumentType.MESSAGE,
        ArgumentType.INTEGER,
        # there's actually a 5th argument which is some pointer, but we don't currently support stack arguments and I
        # also don't know enough about what it points to to edit it
    ]),
    'PickUpMedItem': Function([
        ArgumentType.GAME_STATE,
        ArgumentType.MED_ITEM,
        ArgumentType.INTEGER,
    ], True),
    'SetMessageId': Function([
        ArgumentType.MESSAGE,
    ]),
    'ChangeStage': Function([
        ArgumentType.GAME_STATE,
        ArgumentType.STAGE,
    ]),
    'GoToRoom': Function([
        ArgumentType.GAME_STATE,
        ArgumentType.MAP,
        ArgumentType.ROOM,
        ArgumentType.INTEGER,  # door sound ID
    ]),
    'PlayMovie': Function([
        ArgumentType.GAME_STATE,
        ArgumentType.MOVIE,
        ArgumentType.INTEGER,
        ArgumentType.INTEGER,
    ]),
    'ShowItemTim': Function([
        ArgumentType.GAME_STATE,
        ArgumentType.INTEGER,  # index in ITEMTIM.CDB
    ]),
    'SaveMenu': Function([
        ArgumentType.GAME_STATE,
        ArgumentType.INTEGER,
        ArgumentType.MESSAGE,
        ArgumentType.INTEGER,
        # unsupported 5th argument
    ]),
}


@dataclass
class GameVersion:
    """Information on the specific version of the game this project was created from and will be exported as"""

    id: str
    region: Region
    language: str
    disc: int
    is_demo: bool = False

    @property
    def exe_name(self) -> str:
        return self.id[:4] + '_' + self.id[5:8] + '.' + self.id[8:]


VERSIONS = [
    GameVersion('SLUS-00986', Region.NTSC_U, 'en-US', 1),
    GameVersion('SLUS-01098', Region.NTSC_U, 'en-US', 2),
    GameVersion('SLUS-01099', Region.NTSC_U, 'en-US', 3),

    GameVersion('SLUS-90077', Region.NTSC_U, 'en-US', 1, is_demo=True),

    GameVersion('SLPS-02192', Region.NTSC_J, 'ja', 1),
    GameVersion('SLPS-02193', Region.NTSC_J, 'ja', 2),
    GameVersion('SLPS-02194', Region.NTSC_J, 'ja', 3),

    GameVersion('SLES-02328', Region.PAL, 'en-GB', 1),
    GameVersion('SLES-12328', Region.PAL, 'en-GB', 2),
    GameVersion('SLES-22328', Region.PAL, 'en-GB', 3),

    GameVersion('SLED-02869', Region.PAL, 'en-GB', 1, is_demo=True),

    GameVersion('SLES-02329', Region.PAL, 'fr', 1),
    GameVersion('SLES-12329', Region.PAL, 'fr', 2),
    GameVersion('SLES-22329', Region.PAL, 'fr', 3),

    GameVersion('SLES-02330', Region.PAL, 'de', 1),
    GameVersion('SLES-12330', Region.PAL, 'de', 2),
    GameVersion('SLES-22330', Region.PAL, 'de', 3),
]

LANG_DISC_MAP = {
    ('en-US', 1): VERSIONS[0],
    ('en-US', 2): VERSIONS[1],
    ('en-US', 3): VERSIONS[2],
    ('ja', 1): VERSIONS[4],
    ('ja', 2): VERSIONS[5],
    ('ja', 3): VERSIONS[6],
    ('en-GB', 1): VERSIONS[7],
    ('en-GB', 2): VERSIONS[8],
    ('en-GB', 3): VERSIONS[9],
    ('fr', 1): VERSIONS[11],
    ('fr', 2): VERSIONS[12],
    ('fr', 3): VERSIONS[13],
    ('de', 1): VERSIONS[14],
    ('de', 2): VERSIONS[15],
    ('de', 3): VERSIONS[16],
}

REGION_ADDRESSES = {
    'en-US': {
        'FontMetrics': 0x80191364,
        'StageMessageIndexes': 0x80191450,
        'ActorModels': 0x80192F18,
        'ActorAnimations': 0x801917B0,
        'ItemArt': 0x80190ED4,
        'KeyItemDescriptions': 0x80192A28,
        'MedItemDescriptions': 0x80192ACC,
        'MapModules': 0x80191BE0,
        'ModuleLoadAddresses': [0x801EC628, 0x801F7D60, 0x80023000, 0x80060000],
        'OptionMenuStart': 0x8019148C,
        'OptionMenuStop': 0x80191714,
        'MenuXScaleStart': 0x801917A4,
        'MenuXScaleStop': 0x801917B0,
        'GameState': 0x801AF308,
        'Movies': 0x80191F78,
        'SetRoomLayout': 0x8012E980,
        'SetCollisionObjects': 0x80121194,
        'GetStateFlag': 0x80128600,
        'GetStageStateFlag': 801284E8,
        'SetStateFlag': 0x80128380,
        'SetStageStateFlag': 0x80128220,
        'ClearStateFlag': 0x8012812C,
        'ClearStageStateFlag': 0x80127F20,
        'PickUpFile': 0x80138DA0,
        'SetMessageId': 0x80129B84,
        'GoToRoom': 0x801201B8,
        'ChangeStage': 0x8012016C,
        'PickUpMedItem': 0x8011E798,
        'PickUpKeyItem': 0x8011E7C4,
        'PlayMovie': 0x8011FE44,
        'ShowItemTim': 0x8015EA7C,
        'SaveMenu': 0x80125928,
    },
    'ja': {
        'FontPages': 0x8019144C,
        'StageMessageIndexes': 0x80191494,
        'ActorModels': 0x80192CE8,
        'ActorAnimations': 0x801914A4,
        'ItemArt': 0x80190EB0,
        'KeyItemDescriptions': 0x80192854,
        'MedItemDescriptions': 0x801928F8,
        'MapModules': 0x801918D4,
        'ModuleLoadAddresses': [0x801EDC28, 0x801F9230, 0x801FEAD0, 0x80023000, 0x80060000],
        'XaDef1': 0x80193870,
        'XaDef2': 0x80193880,
        'XaDef3': 0x801938D0,
        'XaDefEnd': 0x8019392C,
        'GameState': 0x801AF910,
        'Movies': 0x80191C9C,
        'SetRoomLayout': 0x8012F400,
        'SetCollisionObjects': 0x80123A70,
        'GetStateFlag': 0x8012A688,
        'GetStageStateFlag': 0x8012A7B0,
        'SetStateFlag': 0x8012A8C8,
        'SetStageStateFlag': 0x8012AA30,
        'ClearStateFlag': 0x8012AB90,
        'ClearStageStateFlag': 0x8012AD10,
        'GoToRoom': 0x80122A5C,
        'ChangeStage': 0x80122A10,
        'PickUpFile': 0x80139F10,
        'PickUpKeyItem': 0x80120F10,
        'PickUpMedItem': 0x80120EE4,
        'PlayMovie': 0x801225F4,
        'ShowItemTim': 0x8015FAA8,
        'SaveMenu': 0x80128174,
    },
}

ADDRESSES = {
    version.id: REGION_ADDRESSES[version.language]
    for version in VERSIONS if version.language in REGION_ADDRESSES and not version.is_demo
}
