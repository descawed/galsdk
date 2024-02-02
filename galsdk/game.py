from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum, auto
from typing import Self

from psx.exe import Region


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
STAGE_MAPS = {
    Stage.A: [0, 1, 2],
    Stage.B: [3, 4],
    Stage.C: [5, 6, 7],
    Stage.D: [8],
}
NUM_MED_ITEMS = len(MED_ITEM_NAMES)
NUM_MAPS = len(MAP_NAMES)
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
    ADDRESS = auto()
    ITEMTIM = auto()


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
        ArgumentType.ITEMTIM,
    ]),
    'SaveMenu': Function([
        ArgumentType.GAME_STATE,
        ArgumentType.INTEGER,
        ArgumentType.MESSAGE,
        ArgumentType.INTEGER,
        # unsupported 5th argument
    ]),
    'LoadAiModule': Function([
        ArgumentType.INTEGER,
    ]),
    'InstallActorAiRoutine': Function([
        ArgumentType.ADDRESS,
        ArgumentType.ADDRESS,
    ]),
    'AttackPlayerRanged': Function([
        ArgumentType.ADDRESS,
        ArgumentType.INTEGER,
        ArgumentType.INTEGER,
        ArgumentType.ADDRESS,
    ]),
    'LoadModuleEntry': Function([
        ArgumentType.INTEGER,
        ArgumentType.INTEGER,
        ArgumentType.ADDRESS,
    ]),
    'StartMeleeAttack': Function([
        ArgumentType.ADDRESS,
        ArgumentType.INTEGER,
    ]),
    'XaPlay': Function([
        ArgumentType.INTEGER,
    ]),
    'XXaPlay': Function([
        ArgumentType.INTEGER,
        ArgumentType.INTEGER,
    ]),
    'ShowTimAndMessage': Function([
        ArgumentType.GAME_STATE,
        ArgumentType.ITEMTIM,
        ArgumentType.MESSAGE,
        ArgumentType.INTEGER,
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
        if self.is_demo:
            if self.region == Region.NTSC_J:
                return 'MAIN.EXE'
            if self.region == Region.NTSC_U:
                return 'GALE.EXE'

        return self.id[:4] + '_' + self.id[5:8] + '.' + self.id[8:]

    @property
    def key_item_tile_counts(self) -> list[int]:
        if self.is_japanese_demo:
            return [29, 17]
        return [self.num_key_items]

    @property
    def num_key_items(self) -> int:
        return 46 if self.is_japanese_demo else 40

    @property
    def key_item_names(self) -> list[str]:
        if self.is_japanese_demo:
            # TODO: verify translation of cut item names
            return [
                'Liquid Explosive',
                'Medical Staff Notes',
                'Security Card',
                'Life Support Data',
                'Pill Case',
                'Freezer Room Key',
                'PPEC Storage Key',  # maybe should call this "Medicine Storage Key"? that agrees with the NA demo
                'Fuse',
                'Unknown #8',  # the icon says は something; can't read the second character
                'Unknown #9',  # can't read the icon
                'G Project Report',
                'Beeject',
                'Security Card (reformatted)',
                'Startup Disk',
                'Security Card (red)',
                'Photo of Parents',
                'Eyeball Lens',
                'Pharmaceutical Factory Key',
                'Two-Headed Snake',
                'Two-Headed Wolf',
                "Rion's test data",
                'Test Lab Key',
                'Two-Headed Eagle',
                "Dr. Lem's Notes",
                "Lilia's image data",
                'Unknown #25',  # some kind of disk
                'Control Room Key',
                'Two-Headed Monkey',
                'Research Lab Key',
                'Familiar recollections',  # no label or icon; name is taken from the model
                'New Replicative Computer Theory',
                'Unknown #31',  # one of these is probably the Letter from Elsa, probably this one
                'Unknown #32',
                "Dr. Pascalle's Diary",
                'Backdoor Key',
                'Door Knob',
                '9 Ball',
                "Mother's Ring",
                "Father's Ring",
                "Lilia's Doll",
                'Metamorphosis',
                'Bedroom Key',
                'Memory Chip A',
                'Memory Chip B',
                'Memory Chip C',
                'Unknown #45',
            ]
        else:
            return [
                'Isolation Ward 15F Map',
                'Security Card',
                'Beeject',
                'Freezer Room Key',
                'PPEC Storage Key',
                'Fuse',
                'Liquid Explosive',
                'Isolation Ward 14F Map',
                'Security Card (reformatted)',
                'Special PPEC Office Key',
                'Isolation Ward 13F Map',
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

    @property
    def num_movies(self) -> int:
        if self.is_demo:
            if self.region == Region.NTSC_J:
                return 54
        if self.region == Region.NTSC_J:
            return 65
        return 66

    @property
    def num_actor_instances(self) -> int:
        if self.is_japanese_demo:
            return 32
        return 138

    @property
    def health_module_index(self) -> int | None:
        if self.region != Region.NTSC_J:
            return None
        if self.is_demo:
            return 138  # 137 also seems to be a type 2 module
        return 129

    @property
    def is_japanese_demo(self) -> bool:
        return self.id == 'SLPM-80289'


VERSIONS = [
    GameVersion('SLUS-00986', Region.NTSC_U, 'en-US', 1),
    GameVersion('SLUS-01098', Region.NTSC_U, 'en-US', 2),
    GameVersion('SLUS-01099', Region.NTSC_U, 'en-US', 3),

    GameVersion('SLUS-90077', Region.NTSC_U, 'en-US', 1, is_demo=True),

    GameVersion('SLPS-02192', Region.NTSC_J, 'ja', 1),
    GameVersion('SLPS-02193', Region.NTSC_J, 'ja', 2),
    GameVersion('SLPS-02194', Region.NTSC_J, 'ja', 3),

    GameVersion('SLPM-80289', Region.NTSC_J, 'ja', 1, is_demo=True),

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

VERSIONS_BY_ID = {version.id: version for version in VERSIONS}

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
        'MenuXScale': 0x801917A4,
        'GameState': 0x801AF308,
        'Movies': 0x80191F78,
        'DefaultActorInstanceHealth': 0x80193E40,
        'SetRoomLayout': 0x8012E980,
        'SetCollisionObjects': 0x80121194,
        'GetStateFlag': 0x80128600,
        'GetStageStateFlag': 801284E8,
        'SetStateFlag': 0x80128380,
        'SetStageStateFlag': 0x80128220,
        'ClearStateFlag': 0x801280A0,
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
        'XaPlay': 0x8012AF18,
        'XXaPlay': 0x8016560C,
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
        'LoadAiModule': 0x8013C708,
        'InstallActorAiRoutine': 0x8013C770,
        'AttackPlayerRanged': 0x8014A180,
        'LoadModuleEntry': 0x8011F7D0,
        'StartMeleeAttack': 0x80144F48,
        'XaPlay': 0x801670D0,
    },
    'de': {
        'FontMetrics': 0x80194178,
        'StageMessageIndexes': 0x80194264,
        'ActorModels': 0x80195DB0,
        'ActorAnimations': 0x801945F8,
        'ItemArt': 0x80193CEC,
        'KeyItemDescriptions': 0x80195850,
        'MedItemDescriptions': 0x801958F4,
        'MapModules': 0x80194A0C,
        'ModuleLoadAddresses': [0x801ED198, 0x801F88E0, 0x80023000, 0x80060000],
        'OptionMenuStart': 0x801942B0,
        'OptionMenuStop': 0x80194538,
        'MenuXScale': 0x801945C8,
        'GameState': 0x801B2468,
        'Movies': 0x80194DAC,
        'DefaultActorInstanceHealth': 0x801974AC,
        'SetRoomLayout': 0x8012C990,
        'SetCollisionObjects': 0x8011F85C,
        'GetStateFlag': 0x80126C88,
        'GetStageStateFlag': 0x80126B70,
        'SetStateFlag': 0x80126A08,
        'SetStageStateFlag': 0x801268A8,
        'ClearStateFlag': 0x80126728,
        'ClearStageStateFlag': 0x801265A8,
        'PickUpFile': 0x80136BF0,
        'SetMessageId': 0x80127E60,
        'GoToRoom': 0x8011E880,
        'ChangeStage': 0x8011E834,
        'PickUpMedItem': 0x8011CE5C,
        'PickUpKeyItem': 0x8011CE88,
        'PlayMovie': 0x8011E50C,
        'ShowItemTim': 0x8015F3D8,
        'SaveMenu': 0x80123FF0,
        'XaPlay': 0x8012921C,
        'XXaPlay': 0x8016836C,
    },
    'en-GB': {
        'FontMetrics': 0x80190750,
        'StageMessageIndexes': 0x8019083C,
        'ActorModels': 0x80192388,
        'ActorAnimations': 0x80190BD0,
        'ItemArt': 0x801902C4,
        'KeyItemDescriptions': 0x80191E28,
        'MedItemDescriptions': 0x80191ECC,
        'MapModules': 0x80190FE4,
        'ModuleLoadAddresses': [0x801E9770, 0x801F4EB8, 0x80023000, 0x80060000],
        'OptionMenuStart': 0x80190888,
        'OptionMenuStop': 0x80190B10,
        'MenuXScale': 0x80190BA0,
        'GameState': 0x801AEA40,
        'Movies': 0x80191384,
        'DefaultActorInstanceHealth': 0x80193A84,
        'SetRoomLayout': 0x8012C990,
        'SetCollisionObjects': 0x8011F85C,
        'GetStateFlag': 0x80126C88,
        'GetStageStateFlag': 0x80126B70,
        'SetStateFlag': 0x80126A08,
        'SetStageStateFlag': 0x801268A8,
        'ClearStateFlag': 0x80126728,
        'ClearStageStateFlag': 0x801265A8,
        'PickUpFile': 0x80136BF0,
        'SetMessageId': 0x80127E60,
        'GoToRoom': 0x8011E880,
        'ChangeStage': 0x8011E834,
        'PickUpMedItem': 0x8011CE5C,
        'PickUpKeyItem': 0x8011CE88,
        'PlayMovie': 0x8011E50C,
        'ShowItemTim': 0x8015D47C,
        'SaveMenu': 0x80123FF0,
        'XaPlay': 0x8012921C,
        'XXaPlay': 0x80164944,
    },
}

ADDRESSES = {
    version.id: REGION_ADDRESSES[version.language]
    for version in VERSIONS if version.language in REGION_ADDRESSES and not version.is_demo
}

ADDRESSES['SLPM-80289'] = {
    'FontPages': 0x8017E8FC,
    'StageMessageIndexes': 0x8017E944,
    'ActorModels': 0x8017F9BC,
    'ActorAnimations': 0x8017E954,
    'ItemArt': 0x8017E260,
    'KeyItemDescriptions': 0x8017F8CC,
    'MapModules': 0x8017ED90,
    'ModuleLoadAddresses': [0x801CB068, 0x801CFD74, 0x801CFFF8],
    'GameState': 0x8019AAA0,
    'Movies': 0x8017EEEC,
    'SetRoomLayout': 0x8013D654,
    'SetCollisionObjects': 0x80135684,
    'GetStateFlag': 0x80139454,
    'SetStateFlag': 0x80139540,
    'ClearStateFlag': 0x801396AC,
    'GoToRoom': 0x80134B10,
    'PickUpFile': 0x80148090,
    'PickUpKeyItem': 0x80133904,
    # med items appear to be added to the inventory manually, not by calling a function
    'PlayMovie': 0x80134778,
    'ShowItemTim': 0x8015763C,
    'ShowTimAndMessage': 0x80134538,
}
