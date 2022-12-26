from __future__ import annotations

import datetime
import io
import json
import re
import shutil
import struct
import tempfile
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable

from galsdk.db import Database
from galsdk.font import Font
from galsdk.manifest import Manifest
from galsdk.model import ACTORS, ActorModel, ItemModel
from galsdk.module import RoomModule
from galsdk.movie import Movie
from galsdk.string import StringDb
from galsdk.xa import XaAudio
from psx import Region
from psx.cd import PsxCd
from psx.config import Config
from psx.exe import Exe


class Stage(str, Enum):
    A = 'A'
    B = 'B'
    C = 'C'
    D = 'D'

    def __str__(self):
        return self.value


@dataclass
class Item:
    id: int
    name: str
    model: ItemModel | None
    description_index: int
    is_key_item: bool = True


KEY_ITEM_NAMES = [
    'Unused',
    'Security Card',
    'Beeject',
    'Freezer Room Key',
    'PPEC Storage Key',
    'Fuse',
    'Liquid Explosive',
    'Unused',
    'Security Card (reformatted)',
    'Special PPEC Office Key',
    'Unused',
    'Test Lab Key',
    'Control Room Key',
    'Research Lab Key',
    'Two-Headed Snake',
    'Two-Headed Monkey',
    'Two-Headed Wolf',
    'Two-Headed Eagle',
    'Unused',
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

NUM_KEY_ITEMS = len(KEY_ITEM_NAMES)
NUM_MED_ITEMS = len(MED_ITEM_NAMES)
NUM_MODULE_SETS = 9
MODULE_ENTRY_SIZE = 8


@dataclass
class GameVersion:
    """Information on the specific version of the game this project was created from and will be exported as"""

    id: str
    region: Region
    language: str
    disc: int
    is_demo: bool = False


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

ADDRESSES = {
    'SLUS-00986': {
        'FontMetrics': 0x80191364,
        'ActorModels': 0x80192F18,
        'ItemArt': 0x80190ED4,
        'KeyItemDescriptions': 0x80192A28,
        'MedItemDescriptions': 0x80192ACC,
        'ModuleSets': 0x80191BE0,
    }
}


class Project:
    """
    Container for the data and metadata of the game being edited

    The Project contains information about the game files being edited, the game version, and various editor metadata
    that isn't stored in the game's own data files. It also provides a version-agnostic interface for manipulating game
    objects and CD images.
    """

    VERSION_MAP = {version.id: version for version in VERSIONS}

    def __init__(self, project_dir: Path, version: GameVersion, actor_models: list[int] = None,
                 module_sets: list[list[dict[str, int]]] = None, last_export_date: datetime.datetime = None):
        self.project_dir = project_dir
        self.version = version
        self.last_export_date = last_export_date or datetime.datetime.utcnow()
        self.actor_models = actor_models or []
        self.module_sets = module_sets or []

    @classmethod
    def _extract_dir(cls, path: str, destination: Path, cd: PsxCd, raw: bool = False):
        for entry in cd.list_dir(path):
            if entry.is_directory:
                sub_path = destination / entry.name
                sub_path.mkdir(exist_ok=True)
                # raw extraction if this is the XA directory in the Japanese version or a movie directory in any version
                cls._extract_dir(entry.path, sub_path, cd, entry.name == 'XA' or entry.name.startswith('MOV'))
            else:
                # remove the CD file version number
                base_name = entry.name.rsplit(';', 1)[0]
                sub_path = destination / base_name
                with sub_path.open('wb') as f:
                    # raw extraction if requested for the dir or if this is the XA archive in the NA version
                    cd.extract(entry.path, f, raw or entry.name == 'XA.MXA;1')

    @classmethod
    def _detect_version(cls, system_cnf: str) -> GameVersion:
        boot_to_game_id = re.compile(r'^BOOT\s*=.+S([a-z]{3})_(\d{3})\.(\d{2});\d+$', re.IGNORECASE)
        for line in system_cnf.splitlines():
            game_id, matches = boot_to_game_id.subn(r'S\1-\2\3', line)
            if matches > 0 and game_id in cls.VERSION_MAP:
                return cls.VERSION_MAP[game_id]
        else:
            raise ValueError('Could not determine game version from SYSTEM.CNF')

    @classmethod
    def detect_files_version(cls, game_dir: str) -> GameVersion:
        return cls._detect_version((Path(game_dir) / 'SYSTEM.CNF').read_text())

    @classmethod
    def detect_cd_version(cls, cd_path: str) -> GameVersion:
        with open(cd_path, 'rb') as f:
            cd = PsxCd(f)
        with io.BytesIO() as buf:
            cd.extract(r'\SYSTEM.CNF;1', buf)
            return cls._detect_version(buf.getvalue().decode())

    @classmethod
    def create_from_cd(cls, cd_path: str, project_dir: str) -> Project:
        """
        Create a new project from the given CD image in the specified directory

        :param cd_path: Path to the CD image to be extracted
        :param project_dir: Path to a directory where the project will be created. The directory will be created if it
            doesn't exist.
        :return: The new project
        """
        with open(cd_path, 'rb') as f:
            cd = PsxCd(f)
        with tempfile.TemporaryDirectory() as d:
            cls._extract_dir('\\', Path(d), cd)
            return cls.create_from_directory(d, cd_path, project_dir)

    @classmethod
    def create_from_directory(cls, game_dir: str, base_image: str, project_dir: str) -> Project:
        """
        Create a new project from a directory containing previously extracted game files

        Ensure that STR videos and XA audio were extracted with raw 2352-byte sectors, otherwise these won't be able to
        be processed correctly.

        :param game_dir: Path to the directory holding the game files
        :param base_image: Path to a CD image that will be used as a template for saving changes to the game
        :param project_dir: Path to a directory where the project will be created. The directory will be created if it
            doesn't exist.
        :return: The new project
        """
        project_path = Path(project_dir)
        game_path = Path(game_dir)

        # determine game version
        version = cls.detect_files_version(game_dir)
        if version.region != Region.NTSC_U or version.is_demo:
            raise NotImplementedError('Currently only the US retail version of the game is supported')

        addresses = ADDRESSES[version.id]
        # locate files we're interested in
        config_path = game_path / 'SYSTEM.CNF'
        game_data = game_path / 'T4'
        display_db_path = game_data / 'DISPLAY.CDB'

        with config_path.open() as f:
            config = Config.read(f)
        boot_path = config.boot.split(':\\')[1].rsplit(';')[0].replace('\\', '/')
        exe_path = game_path / boot_path
        with exe_path.open('rb') as f:
            exe = Exe.read(f)

        display_db = Database()
        with display_db_path.open('rb') as f:
            display_db.read(f)

        # prepare project directory
        export_dir = project_path / 'export'
        export_dir.mkdir(exist_ok=True)
        shutil.copy(base_image, export_dir / 'output.bin')
        shutil.copy(display_db_path, export_dir)

        font_image_path = project_path / 'font.tim'
        with font_image_path.open('wb') as f:
            f.write(display_db[4])
        font_path = project_path / 'font.json'
        font_metrics = exe[addresses['FontMetrics']:addresses['FontMetrics']+224]
        font = {'image': 'font.tim', 'widths': {}}
        for i, width in enumerate(font_metrics):
            font['widths'][i + 0x20] = width
        with font_path.open('w') as f:
            json.dump(font, f)

        stages_dir = project_path / 'stages'
        stages_dir.mkdir(exist_ok=True)
        string_offset = 5
        for i, stage in enumerate(Stage):
            stage_dir = stages_dir / stage
            stage_dir.mkdir(exist_ok=True)
            bg_dir = stage_dir / 'backgrounds'
            bg_dir.mkdir(exist_ok=True)
            movie_dir = stage_dir / 'movies'
            if movie_dir.is_dir():
                shutil.rmtree(movie_dir)

            movie_src = game_data / ('MOV' if stage == Stage.A else f'MOV_{stage}')
            # depending on which disc we're on, some of these directories won't exist
            if movie_src.exists():
                shutil.copytree(movie_src, movie_dir)

            bg_db_path = game_data / f'BGTIM_{stage}.CDB'
            Manifest.from_database(bg_dir, bg_db_path, 'TDB')

            string_path = stage_dir / 'strings.db'
            with string_path.open('wb') as f:
                f.write(display_db[string_offset + i])

        model_db_path = game_data / 'MODEL.CDB'
        model_dir = project_path / 'models'
        model_dir.mkdir(exist_ok=True)
        Manifest.from_database(model_dir, model_db_path)
        # only actors without a manually-assigned model index are in the list
        num_actors = sum(1 if actor.model_index is None else 0 for actor in ACTORS)
        actor_models = list(
            struct.unpack(f'{num_actors}h', exe[addresses['ActorModels']:addresses['ActorModels'] + 2 * num_actors])
        )

        raw_item_art = struct.unpack(f'{4 * NUM_KEY_ITEMS}I',
                                     exe[addresses['ItemArt']:addresses['ItemArt'] + 16 * NUM_KEY_ITEMS])
        item_art = [(raw_item_art[i], raw_item_art[i+1], raw_item_art[i+2], raw_item_art[i+3])
                    for i in range(0, len(raw_item_art), 4)]

        key_item_descriptions = list(
            struct.unpack(f'{NUM_KEY_ITEMS}I',
                          exe[addresses['KeyItemDescriptions']:addresses['KeyItemDescriptions'] + 4 * NUM_KEY_ITEMS])
        )
        med_item_descriptions = list(
            struct.unpack(f'{NUM_MED_ITEMS}I',
                          exe[addresses['MedItemDescriptions']:addresses['MedItemDescriptions'] + 4 * NUM_MED_ITEMS])
        )

        item_path = project_path / 'item.json'
        items = []
        for i in range(NUM_KEY_ITEMS):
            items.append({'id': i, 'model': item_art[i][0], 'flags': item_art[i][3],
                          'description': key_item_descriptions[i]})
        for i in range(NUM_MED_ITEMS):
            items.append({'id': i, 'model': None, 'flags': 0, 'description': med_item_descriptions[i]})
        with item_path.open('w') as f:
            json.dump(items, f)

        module_dir = project_path / 'modules'
        module_dir.mkdir(exist_ok=True)

        module_db_path = game_data / 'MODULE.BIN'
        module_manifest = Manifest.from_database(module_dir, module_db_path)
        for i, module_file in enumerate(module_manifest):
            # FIXME: figure out how the module sets work and pull the list from there
            with module_file.path.open('rb') as f:
                module = RoomModule.load(f)
            if module.is_valid:
                module_manifest.rename(i, module.name)
        module_manifest.save()

        module_set_addr = addresses['ModuleSets']
        module_set_addrs = struct.unpack(f'{NUM_MODULE_SETS}I',
                                         exe[module_set_addr:module_set_addr + 4 * NUM_MODULE_SETS])
        module_sets = []
        for i in range(len(module_set_addrs)):
            this_addr = module_set_addrs[i]
            if i + 1 >= NUM_MODULE_SETS:
                next_addr = module_set_addr
            else:
                next_addr = module_set_addrs[i + 1]
            num_modules = (next_addr - this_addr) // MODULE_ENTRY_SIZE
            raw_entries = struct.unpack('2I' * num_modules, exe[this_addr:next_addr])
            module_sets.append([
                {'index': raw_entries[j], 'entry_point': raw_entries[j + 1]}
                for j in range(0, len(raw_entries), 2)
            ])

        menu_dir = project_path / 'menu'
        menu_dir.mkdir(exist_ok=True)

        menu_db_path = game_data / 'MENU.CDB'
        # TODO: figure out what all of the stuff in here does
        menu_manifest = Manifest.from_database(menu_dir, menu_db_path)
        # sub-databases
        item_art_dir = menu_dir / 'item_art'
        item_art_dir.mkdir(exist_ok=True)
        item_art_file = menu_manifest[53]
        item_art_manifest = Manifest.from_tim_database(item_art_dir, item_art_file.path, True)
        item_art_manifest.rename(36, 'medicine_icons')
        item_art_manifest.rename(37, 'key_item_icons')
        item_art_manifest.rename(41, 'ability_icons')
        item_art_manifest.save()

        sound_dir = project_path / 'sound'
        sound_dir.mkdir(exist_ok=True)
        sound_db_path = game_data / 'SOUND.CDB'
        sound_manifest = Manifest.from_database(sound_dir, sound_db_path)
        # make sub-databases for all the VAB DBs
        for i, entry in enumerate(sound_manifest):
            vab_dir = sound_dir / str(i)
            vab_dir.mkdir(exist_ok=True)

        voice_dir = project_path / 'voice'
        voice_dir.mkdir(exist_ok=True)

        xa_map = display_db[version.disc]
        mxa_path = game_data / 'XA.MXA'
        buf = io.BytesIO(xa_map)
        Manifest.from_xa_database(voice_dir, buf, mxa_path)

        project = cls(project_path, version, actor_models, module_sets)
        project.save()
        return project

    @classmethod
    def open(cls, project_dir: str) -> Project:
        """
        Open a project that was previously created in a given directory

        :param project_dir: Path to the project directory
        :return: The opened project
        """
        project_path = Path(project_dir)
        with (project_path / 'project.json').open() as f:
            project_info = json.load(f)
        version = GameVersion(**project_info['version'])
        last_export_date = datetime.datetime.fromisoformat(project_info['last_export_date'])
        actor_models = project_info['actor_models']
        module_sets = project_info.get('module_sets', [])
        return cls(project_path, version, actor_models, module_sets, last_export_date)

    @property
    def all_actor_models(self) -> set[int]:
        all_actor_models = set(self.actor_models)
        for actor in ACTORS:
            if actor.model_index is not None:
                all_actor_models.add(actor.model_index)
        return all_actor_models

    def save(self):
        """Save project metadata"""
        with (self.project_dir / 'project.json').open('w') as f:
            json.dump({
                'version': asdict(self.version),
                'last_export_date': self.last_export_date.isoformat(),
                'actor_models': self.actor_models,
                'module_sets': self.module_sets,
            }, f)

    def get_stage_backgrounds(self, stage: Stage) -> Manifest:
        """
        Get the background manifest for a particular stage

        :param stage: The stage for which to get the background manifest
        :return: The manifest of background files
        """
        return Manifest.load_from(self.project_dir / 'stages' / stage / 'backgrounds')

    def get_stage_movies(self, stage: Stage) -> Iterable[Movie]:
        for path in (self.project_dir / 'stages' / stage / 'movies').glob('*.STR'):
            yield Movie(path)

    def get_voice_audio(self) -> Iterable[XaAudio]:
        manifest = Manifest.load_from(self.project_dir / 'voice')
        for f in manifest:
            yield XaAudio(f.path)

    def get_font(self) -> Font:
        return Font.load(self.project_dir)

    def get_stage_strings(self, stage: Stage) -> StringDb:
        path = self.project_dir / 'stages' / stage / 'strings.db'
        db = StringDb()
        with path.open('rb') as f:
            db.read(f)
        return db

    def get_stage_rooms(self, stage: Stage) -> Iterable[RoomModule]:
        manifest = Manifest.load_from(self.project_dir / 'modules')
        for manifest_file in manifest:
            if manifest_file.name[0] == stage:
                with manifest_file.path.open('rb') as f:
                    yield RoomModule.load(f)

    def get_actor_models(self) -> Iterable[ActorModel]:
        manifest = Manifest.load_from(self.project_dir / 'models')
        for actor in ACTORS:
            if actor.model_index is None:
                model_index = self.actor_models[actor.id]
            else:
                model_index = actor.model_index
            model_file = manifest[model_index]
            with model_file.path.open('rb') as f:
                yield ActorModel.read(actor, f)

    def get_item_art(self) -> Manifest:
        return Manifest.load_from(self.project_dir / 'menu' / 'item_art')

    def get_items(self) -> Iterable[Item]:
        model_manifest = Manifest.load_from(self.project_dir / 'models')
        json_path = self.project_dir / 'item.json'
        with json_path.open() as f:
            info = json.load(f)
        for entry in info:
            is_key_item = entry['model'] is not None
            if is_key_item:
                name = KEY_ITEM_NAMES[entry['id']]
                model_file = model_manifest[entry['model']]
                with model_file.path.open('rb') as f:
                    model = ItemModel.read(name, f, entry['flags'] & 1 == 0)
            else:
                name = MED_ITEM_NAMES[entry['id']]
                model = None
            yield Item(entry['id'], name, model, entry['description'], is_key_item)

    def get_all_models(self) -> tuple[dict[int, ActorModel], dict[int, ItemModel], dict[int, ItemModel]]:
        model_manifest = Manifest.load_from(self.project_dir / 'models')
        json_path = self.project_dir / 'item.json'
        with json_path.open() as f:
            item_info = json.load(f)

        actor_models = {}
        for actor in ACTORS:
            if actor.model_index is None:
                model_index = self.actor_models[actor.id]
            else:
                model_index = actor.model_index
            if model_index not in actor_models:
                actor_models[model_index] = actor

        item_models = {}
        for entry in item_info:
            if entry['model'] is not None and entry['model'] not in item_models:
                item_models[entry['model']] = (KEY_ITEM_NAMES[entry['id']], entry['flags'] & 1 == 0)

        actors = {}
        items = {}
        other = {}
        for i, model_file in enumerate(model_manifest):
            with model_file.path.open('rb') as f:
                if i in actor_models:
                    actors[i] = ActorModel.read(actor_models[i], f)
                elif i in item_models:
                    name, use_transparency = item_models[i]
                    items[i] = ItemModel.read(name, f, use_transparency)
                else:
                    other[i] = ItemModel.read(str(i), f)

        return actors, items, other
