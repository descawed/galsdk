from __future__ import annotations

import datetime
import functools
import io
import json
import re
import shutil
import struct
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePath
from typing import Iterable

from galsdk import file
from galsdk.db import Database
from galsdk.credits import Credits
from galsdk.font import Font, LatinFont, JapaneseFont
from galsdk.game import (Stage, MED_ITEM_NAMES, NUM_MED_ITEMS, NUM_MAPS, MAP_NAMES, MODULE_ENTRY_SIZE, STAGE_MAPS,
                         GameVersion, VERSIONS, ADDRESSES)
from galsdk.manifest import FromManifest, Manifest
from galsdk.menu import ComponentInstance, Menu
from galsdk.model import ACTORS, ActorModel, ItemModel
from galsdk.module import RoomModule
from galsdk.movie import Movie
from galsdk.string import StringDb, LatinStringDb, JapaneseStringDb
from galsdk.tim import TimDb, TimFormat
from galsdk.vab import VabDb
from galsdk.xa import XaAudio, XaDatabase, XaRegion
from psx.cd import Patch, PsxCd
from psx.exe import Exe, Region


@dataclass
class Item:
    id: int
    name: str
    model: ItemModel | None
    description_index: int
    is_key_item: bool = True


@dataclass
class ActorGraphics:
    model_index: int
    anim_index: int


@dataclass
class MapRoom:
    room_index: int
    module_index: int
    entry_point: int

    def to_bytes(self) -> bytes:
        return self.module_index.to_bytes(4, 'little') + self.entry_point.to_bytes(4, 'little')


@dataclass
class Map:
    index: int
    name: str
    rooms: list[MapRoom]

    def to_bytes(self) -> bytes:
        return b''.join(room.to_bytes() for room in self.rooms)


class Project:
    """
    Container for the data and metadata of the game being edited

    The Project contains information about the game files being edited, the game version, and various editor metadata
    that isn't stored in the game's own data files. It also provides a version-agnostic interface for manipulating game
    objects and CD images.
    """

    VERSION_MAP = {version.id: version for version in VERSIONS}

    def __init__(self, project_dir: Path, version: GameVersion, actor_graphics: list[ActorGraphics] = None,
                 module_sets: list[list[dict[str, int]]] = None, x_scales: list[int] = None,
                 option_menu: list[ComponentInstance] = None, last_export_date: datetime.datetime = None,
                 create_date: datetime.datetime = None):
        self.project_dir = project_dir
        self.version = version
        self.create_date = create_date or datetime.datetime.now(datetime.UTC)
        self.last_export_date = last_export_date or datetime.datetime.now(datetime.UTC)
        self.actor_graphics = actor_graphics or []
        self.module_sets = module_sets or []
        self.x_scales = x_scales or []
        self.option_menu = option_menu or []
        self.addresses = ADDRESSES[self.version.id]

    @classmethod
    def _extract_dir(cls, path: str, destination: Path, cd: PsxCd, raw: bool = False, extend: bool = False):
        for entry in cd.list_dir(path):
            if entry.is_directory:
                sub_path = destination / entry.name
                sub_path.mkdir(exist_ok=True)
                # raw extraction if this is the XA directory in the Japanese version or a movie directory in any version
                is_xa = entry.name == 'XA'
                cls._extract_dir(entry.path, sub_path, cd, is_xa or entry.name.startswith('MOV'), is_xa)
            else:
                # remove the CD file version number
                base_name = entry.name.rsplit(';', 1)[0]
                sub_path = destination / base_name
                with sub_path.open('wb') as f:
                    # raw extraction if requested for the dir or if this is the XA archive in the NA version. we also
                    # set the extend flag because the filesystem doesn't record the true full size of XA.MXA.
                    is_xa = entry.name == 'XA.MXA;1'
                    cd.extract(entry.path, f, raw or is_xa, extend or is_xa)

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
            cd = PsxCd(f, ignore_invalid=True)
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
            cd = PsxCd(f, ignore_invalid=True)
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

        project_path.mkdir(exist_ok=True)

        # determine game version
        version = cls.detect_files_version(game_dir)
        if version.language == 'fr' or (version.is_demo and version.region == Region.PAL):
            raise NotImplementedError('The French version and the European demo are not currently supported')

        addresses = ADDRESSES[version.id]
        # locate files we're interested in
        config_path = game_path / 'SYSTEM.CNF'
        game_data = game_path / 'T4'

        exe_path = (game_data if version.is_demo or version.region == Region.NTSC_J else game_path) / version.exe_name
        with exe_path.open('rb') as f:
            exe = Exe.read(f)

        boot_dir = project_path / 'boot'
        boot_dir.mkdir(exist_ok=True)
        shutil.copy(exe_path, boot_dir / exe_path.name)
        shutil.copy(config_path, boot_dir / config_path.name)

        art_dir = project_path / 'art'
        art_dir.mkdir(exist_ok=True)
        art_dbs = ['BGTIM_A.CDB', 'BGTIM_B.CDB', 'BGTIM_C.CDB', 'BGTIM_D.CDB', 'CARD.CDB', 'DISPLAY.CDB', 'FONT.CDB',
                   'ITEMTIM.CDB', 'MAIN_TEX.CDB', 'MENU.CDB', 'TIT.CDB']

        for art_db_name in art_dbs:
            art_db_path = game_data / art_db_name
            if not art_db_path.exists():  # several of these only exist in the Japanese version
                continue

            with art_db_path.open('rb') as f:
                art_db = Database.read(f)
            project_art_dir = art_dir / art_db_path.stem
            project_art_dir.mkdir(exist_ok=True)
            art_manifest = Manifest.from_archive(project_art_dir, art_db_path.stem, art_db,
                                                 sniff=[LatinStringDb, XaDatabase, Menu, TimDb, TimFormat, Credits],
                                                 original_path=art_db_path)

            if version.region == Region.NTSC_J and art_db_path.name.startswith('BGTIM_'):
                # we want every entry in the BGTIM archives to be a manifest, but in the Japanese version, the entries
                # are TIM streams, and we treat TIM streams with one element as just individual TIMs, which aren't
                # archives. so, we have to go back and put all the affected TIMs in a container.
                new_manifests = {}
                for i, mf in enumerate(art_manifest):
                    if mf.is_manifest:
                        continue

                    new_path = mf.path.with_suffix('.TMM')
                    new_path.mkdir(exist_ok=True)
                    original_path = new_path / 'original.bin'
                    shutil.copy(mf.path, original_path)
                    # FIXME: passing the metadata like this is a hack because it's supposed to come from the TimDb
                    #  instance that was unpacked
                    sub_manifest = Manifest(new_path, f'{art_manifest.name}_{mf.name}', 'tmm',
                                            original_path, {'fmt': '.TMM'})
                    sub_manifest.add(mf.path, 0, mf.name, '.TIM')
                    sub_manifest.save()
                    new_manifests[i] = (mf.name, sub_manifest)

                with art_manifest:
                    for i, (name, sub_manifest) in new_manifests.items():
                        del art_manifest[i]
                        art_manifest.add_manifest(sub_manifest, i, name, '.TMM')

        display_manifest = Manifest.load_from(art_dir / 'DISPLAY')

        num_stage_ints = len(Stage)
        raw_message_indexes = exe[addresses['StageMessageIndexes']:addresses['StageMessageIndexes'] + 4*num_stage_ints]
        message_indexes = list(struct.unpack(f'<{num_stage_ints}I', raw_message_indexes))

        message_dir = project_path / 'messages'
        message_dir.mkdir(exist_ok=True)
        message_db_path = game_data / 'MES.CDB'
        if message_db_path.exists():
            with message_db_path.open('rb') as f:
                message_db = Database.read(f)
            message_manifest = Manifest.from_archive(message_dir, 'MES', message_db, original_path=message_db_path)
            message_manifest.rename(0, 'Debug')
            message_manifest.save()
        else:
            # FIXME: this file also exists in the Japanese demo
            ge_db_path = game_data / 'GE.CDB'  # debug strings only present in the US version
            if ge_db_path.exists():
                with ge_db_path.open('rb') as f:
                    ge_db = Database.read(f)
                ge_manifest = Manifest.from_archive(message_dir, 'GE', ge_db, original_path=ge_db_path)
                ge_manifest.rename(0, 'GE')
                ge_manifest.save()
            message_manifest = display_manifest

        font_path = project_path / 'font.json'
        if version.region == Region.NTSC_J:
            font_manifest = Manifest.load_from(art_dir / 'FONT')
            raw_font_pages = exe[addresses['FontPages']:addresses['FontPages']+4*num_stage_ints]
            font_pages = list(struct.unpack(f'<{num_stage_ints}I', raw_font_pages))
            page_mapping = []
            for i, page in enumerate(font_pages):
                kanji_path = font_manifest[page].path
                page_mapping.append({'image': str(kanji_path.relative_to(project_path)), 'index': page})

            basic_font = 5 if version.is_demo else 2
            font = {'image': str(font_manifest[basic_font].path.relative_to(project_path)), 'kanji': page_mapping}
            with font_path.open('w') as f:
                json.dump(font, f)
        else:
            if version.region == Region.NTSC_U:
                font_image_index = 4
            else:
                font_image_index = 1
            font_metrics = exe[addresses['FontMetrics']:addresses['FontMetrics']+224]
            font = {'image': str(display_manifest[font_image_index].path.relative_to(project_path)), 'widths': {}}
            for i, width in enumerate(font_metrics):
                font['widths'][i + 0x20] = width
            with font_path.open('w') as f:
                json.dump(font, f)

        stages_dir = project_path / 'stages'
        stages_dir.mkdir(exist_ok=True)
        for i, stage in enumerate(Stage):
            stage_dir = stages_dir / stage
            stage_dir.mkdir(exist_ok=True)
            movie_dir = stage_dir / 'movies'
            if movie_dir.is_dir():
                shutil.rmtree(movie_dir)

            movie_src = game_data / ('MOV' if stage == Stage.A else f'MOV_{stage}')
            # depending on which disc we're on, some of these directories won't exist
            if movie_src.exists():
                shutil.copytree(movie_src, movie_dir)

            manifest_path = art_dir / f'BGTIM_{stage}'

            stage_info_path = stage_dir / 'stage.json'
            stage_info = {
                'index': i,
                'strings': str(message_manifest[message_indexes[i]].path.relative_to(project_path)),
                'background': str(manifest_path.relative_to(project_path)),
            }
            with stage_info_path.open('w') as f:
                json.dump(stage_info, f)

        model_db_path = game_data / 'MODEL.CDB'
        model_dir = project_path / 'models'
        model_dir.mkdir(exist_ok=True)
        with model_db_path.open('rb') as f:
            model_db = Database.read(f)
        Manifest.from_archive(model_dir, 'MODEL', model_db, sniff=[ActorModel, ItemModel], original_path=model_db_path)
        # only actors without a manually-assigned model index are in the list
        num_actors = sum(1 if actor.model_index is None else 0 for actor in ACTORS)
        actor_models = list(
            struct.unpack(f'<{num_actors}h', exe[addresses['ActorModels']:addresses['ActorModels'] + 2 * num_actors])
        )
        actor_animations = list(
            struct.unpack(f'<{num_actors}h',
                          exe[addresses['ActorAnimations']:addresses['ActorAnimations'] + 2 * num_actors])
        )
        actor_graphics = [ActorGraphics(model_index, anim_index)
                          for model_index, anim_index in zip(actor_models, actor_animations, strict=True)]

        anim_db_path = game_data / 'MOT.CDB'
        anim_dir = project_path / 'animations'
        anim_dir.mkdir(exist_ok=True)
        with anim_db_path.open('rb') as f:
            anim_db = Database.read(f)
        with Manifest.from_archive(anim_dir, 'MOT', anim_db, recursive=False,
                                   original_path=anim_db_path) as anim_manifest:
            renamed_indexes = set()
            for i, anim_index in enumerate(actor_animations):
                if anim_index not in renamed_indexes:
                    # we don't rename the file on disk because the actor names can contain special characters
                    anim_manifest.rename(anim_index, ACTORS[i].name, False)
                    renamed_indexes.add(anim_index)

        module_dir = project_path / 'modules'
        module_dir.mkdir(exist_ok=True)

        module_db_path = game_data / 'MODULE.BIN'
        with module_db_path.open('rb') as f:
            module_db = Database.read(f)
        module_manifest = Manifest.from_archive(module_dir, 'MODULE', module_db, original_path=module_db_path)

        maps = cls._get_maps(addresses['MapModules'], exe)

        rooms_seen = set()
        all_modules_path = Path.cwd() / 'data' / 'module'
        module_metadata = None
        if (candidate := all_modules_path / version.id).exists():
            module_metadata = candidate
        elif (candidate := all_modules_path / version.language).exists() and not version.is_demo:
            module_metadata = candidate

        if module_metadata is not None:
            shutil.copytree(module_metadata, module_dir, dirs_exist_ok=True)

        metadata_paths = {}
        with module_manifest:
            for modules in maps:
                for module_entry in modules:
                    index = module_entry['index']
                    if index in rooms_seen:
                        continue

                    rooms_seen.add(index)
                    module_file = module_manifest[index]
                    metadata_path = module_file.path.with_suffix('.json')
                    if metadata_path.exists():
                        module = RoomModule.load_with_metadata(module_file.path, version.id)
                    else:
                        with module_file.path.open('rb') as f:
                            module = RoomModule.parse(f, version.id, module_entry['entry_point'])
                    if not module.is_empty:
                        try:
                            module_manifest.rename(index, module.name, ext=module.suggested_extension)
                        except KeyError:
                            module_manifest.rename(index, f'{module.name}_{index}', ext=module.suggested_extension)

                        with metadata_path.open('w') as f:
                            module.save_metadata(f)
                        metadata_paths[index] = metadata_path

        # now that the manifest and renames have been saved, rename all the metadata files as well
        for index, old_metadata_path in metadata_paths.items():
            new_metadata_path = module_manifest[index].path.with_suffix('.json')
            old_metadata_path.rename(new_metadata_path)

        x_scales = []
        option_menu = []
        if version.region != Region.NTSC_J:
            # read menu data
            x_scale_start = addresses['MenuXScale']
            x_scale_stop = x_scale_start + 3 * 4
            x_scales = list(struct.unpack('<3I', exe[x_scale_start:x_scale_stop]))
            raw_instances = exe[addresses['OptionMenuStart']:addresses['OptionMenuStop']]
            for i in range(0, len(raw_instances), 12):
                x, y, component_index, r, g, b, draw = struct.unpack('<2H4BI', raw_instances[i:i + 12])
                option_menu.append(ComponentInstance(x, y, component_index, (r, g, b), draw))

            if version.region == Region.NTSC_U:
                option_menu_index = 3
            else:
                option_menu_index = 2
            display_manifest.rename(option_menu_index, 'Option')
            display_manifest.save()

        menu_manifest = Manifest.load_from(art_dir / 'MENU')
        with menu_manifest:
            # sub-databases
            if version.region == Region.NTSC_J:
                item_art_id = 8
            else:
                item_art_id = 53
                if version.region == Region.NTSC_U:
                    menu_manifest.rename(55, 'Inventory')
            menu_manifest.rename(item_art_id, 'item_art')
            item_art_dir = menu_manifest[item_art_id].path
            item_art_manifest = Manifest.load_from(item_art_dir)
            with item_art_manifest:
                if version.is_japanese_demo:
                    item_art_manifest.rename(0, 'key_item_icons_a')
                    item_art_manifest.rename(1, 'key_item_icons_b')
                else:
                    item_art_manifest.rename(36, 'medicine_icons')
                    item_art_manifest.rename(37, 'key_item_icons')
                    item_art_manifest.rename(41, 'ability_icons')

        num_key_items = version.num_key_items
        raw_item_art = struct.unpack(f'<{4 * num_key_items}I',
                                     exe[addresses['ItemArt']:addresses['ItemArt'] + 16 * num_key_items])
        item_art = [(raw_item_art[i], raw_item_art[i + 1], raw_item_art[i + 2], raw_item_art[i + 3])
                    for i in range(0, len(raw_item_art), 4)]

        key_item_descriptions = list(
            struct.unpack(f'<{num_key_items}I',
                          exe[addresses['KeyItemDescriptions']:addresses['KeyItemDescriptions'] + 4 * num_key_items])
        )
        if 'MedItemDescriptions' in addresses:
            med_item_descriptions = list(
                struct.unpack(f'<{NUM_MED_ITEMS}I',
                              exe[addresses['MedItemDescriptions']:addresses['MedItemDescriptions'] + 4 * NUM_MED_ITEMS]
                              )
            )
        else:
            med_item_descriptions = []
        if version.region == Region.NTSC_J:
            # the Japanese version uses offsets instead of indexes, so we need to convert
            menu_db_path = game_data / 'MENU.CDB'
            with menu_db_path.open('rb') as f:
                menu_db = Database.read(f)
            item_art_db = TimDb.read_bytes(menu_db[item_art_id],
                                           fmt=TimDb.Format.from_extension(item_art_manifest.type))
            for i in range(len(key_item_descriptions)):
                key_item_descriptions[i] = item_art_db.get_index_from_offset(key_item_descriptions[i])
            for i in range(len(med_item_descriptions)):
                med_item_descriptions[i] = item_art_db.get_index_from_offset(med_item_descriptions[i])

        item_path = project_path / 'item.json'
        items = []
        for i in range(len(item_art)):
            items.append({'id': i, 'model': item_art[i][0], 'flags': item_art[i][3],
                          'description': key_item_descriptions[i]})
        for i in range(len(med_item_descriptions)):
            items.append({'id': i, 'model': None, 'flags': 0, 'description': med_item_descriptions[i]})
        with item_path.open('w') as f:
            json.dump(items, f)

        sound_dir = project_path / 'sound'
        sound_dir.mkdir(exist_ok=True)
        sound_db_path = game_data / 'SOUND.CDB'
        with sound_db_path.open('rb') as f:
            sound_db = Database.read(f)
        Manifest.from_archive(sound_dir, 'SOUND', sound_db, sniff=[VabDb], original_path=sound_db_path)

        voice_dir = project_path / 'voice'
        voice_dir.mkdir(exist_ok=True)

        # demos have no XA audio
        if not version.is_demo:
            if version.region == Region.NTSC_J:
                xa_dir = game_data / 'XA'
                for xa_bin in xa_dir.iterdir():
                    if xa_bin.suffix == '.BIN':
                        shutil.copy(xa_bin, voice_dir)
            else:
                shutil.copy(game_data / 'XA.MXA', voice_dir)
        Manifest.from_directory(voice_dir, 'XA')

        # prepare export directory
        export_dir = project_path / 'export'
        export_dir.mkdir(exist_ok=True)
        output_path = export_dir / 'output.bin'
        shutil.copy(base_image, output_path)
        # ensure that the modified date on the export image is later than all the other files we just created, because
        # that's how we identify what's changed
        output_path.touch(exist_ok=True)

        project = cls(project_path, version, actor_graphics, maps, x_scales, option_menu)
        project.save()
        return project

    @staticmethod
    def _get_maps(module_set_addr: int, exe: Exe) -> list[list[dict[str, int]]]:
        module_set_addrs = struct.unpack(f'<{NUM_MAPS}I',
                                         exe[module_set_addr:module_set_addr + 4 * NUM_MAPS])
        maps = []
        for i in range(len(module_set_addrs)):
            this_addr = module_set_addrs[i]
            next_addr = module_set_addr if i + 1 >= NUM_MAPS else module_set_addrs[i + 1]
            num_modules = (next_addr - this_addr) // MODULE_ENTRY_SIZE
            raw_entries = struct.unpack('<' + ('2I' * num_modules), exe[this_addr:next_addr])
            maps.append([
                {'index': raw_entries[j], 'entry_point': raw_entries[j + 1]}
                for j in range(0, len(raw_entries), 2)
            ])
        return maps

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
        create_date = datetime.datetime.fromisoformat(project_info['create_date'])
        last_export_date = datetime.datetime.fromisoformat(project_info['last_export_date'])
        actor_graphics = [ActorGraphics(**actor) for actor in project_info['actor_graphics']]
        module_sets = project_info.get('module_sets', [])
        x_scales = project_info.get('x_scales', [])
        option_menu = [ComponentInstance(**instance) for instance in project_info.get('option_menu', [])]
        return cls(project_path, version, actor_graphics, module_sets, x_scales, option_menu, last_export_date,
                   create_date)

    @property
    def all_actor_models(self) -> set[int]:
        all_actor_models = set(actor.model_index for actor in self.actor_graphics)
        for actor in ACTORS:
            if actor.model_index is not None:
                all_actor_models.add(actor.model_index)
        return all_actor_models

    def save(self):
        """Save project metadata"""
        with (self.project_dir / 'project.json').open('w') as f:
            json.dump({
                'version': asdict(self.version),
                'create_date': self.create_date.isoformat(),
                'last_export_date': self.last_export_date.isoformat(),
                'actor_graphics': [asdict(instance) for instance in self.actor_graphics],
                'module_sets': self.module_sets,
                'x_scales': self.x_scales,
                'option_menu': [asdict(instance) for instance in self.option_menu],
            }, f)

    def get_stage_backgrounds(self, stage: Stage) -> Manifest:
        """
        Get the background manifest for a particular stage

        :param stage: The stage for which to get the background manifest
        :return: The manifest of background files
        """
        path = self.project_dir / 'stages' / stage / 'stage.json'
        with path.open('r') as f:
            stage_info = json.load(f)
        if 'background' in stage_info:
            return Manifest.load_from(self.project_dir / Path(stage_info['background']))
        # old project
        return Manifest.load_from(self.project_dir / 'stages' / stage / 'backgrounds')

    def get_stage_movies(self, stage: Stage) -> Iterable[Movie]:
        for path in sorted((self.project_dir / 'stages' / stage / 'movies').glob('*.STR')):
            yield Movie(path)

    def get_xa_databases(self) -> list[XaDatabase]:
        if self.version.is_demo:
            return []

        voice_dir = self.project_dir / 'voice'
        voice_manifest = Manifest.load_from(voice_dir)

        xa_dbs = []
        if self.version.region == Region.NTSC_J:
            exe_path = self.project_dir / 'boot' / self.version.exe_name
            with exe_path.open('rb') as f:
                exe = Exe.read(f)

            region_sets = XaRegion.get_jp_xa_regions(self.addresses, self.version.disc, exe)

            for mf in voice_manifest:
                index = int(mf.name[-2:])
                xa_dbs.append(XaDatabase(region_sets[index], mf.path.read_bytes()))
        else:
            display_manifest = Manifest.load_from(self.project_dir / 'art' / 'DISPLAY')
            disc_index = self.version.disc - 1
            if self.version.region == Region.NTSC_U:
                xa_map_offset = 0
            else:
                xa_map_offset = 4
            xa_map = display_manifest[xa_map_offset + disc_index].path.read_bytes()
            for mf in voice_manifest:
                xa_db = XaDatabase.read_bytes(xa_map)
                xa_db.set_data(mf.path.read_bytes())
                xa_dbs.append(xa_db)

        return xa_dbs

    def get_voice_audio(self) -> Iterable[XaAudio]:
        extract_dir = self.project_dir / 'voice' / 'extract'
        shutil.rmtree(extract_dir, ignore_errors=True)
        extract_dir.mkdir(exist_ok=True)
        for i, xa_db in enumerate(self.get_xa_databases()):
            db_dir = extract_dir / str(i)
            db_dir.mkdir(exist_ok=True)
            for j in range(len(xa_db)):
                xa_path = db_dir / f'{j:03}'
                xa_db.unpack_one(xa_path, j)
                yield XaAudio(xa_path)

    def export_xa_mxa(self):
        out_db = XaDatabase()
        for xa_db in self.get_xa_databases():
            out_db.extend(xa_db)

        export_dir = self.project_dir / 'export'
        with (export_dir / f'{self.version.disc - 1:03}.XDB').open('wb') as f:
            out_db.write(f)
        (export_dir / 'XA.MXA').write_bytes(out_db.data)

    def get_font(self) -> Font:
        font_type = JapaneseFont if self.version.region == Region.NTSC_J else LatinFont
        return font_type.load(self.project_dir)

    @functools.cache
    def get_stage_strings(self, stage: Stage) -> FromManifest[StringDb]:
        """
        Get the string database for the given stage.

        :param stage: The stage for which to get the string database
        :return: The string database. Subsequent calls to this function for the same stage always return the same
        database object.
        """

        path = self.project_dir / 'stages' / stage / 'stage.json'
        with path.open('r') as f:
            stage_info = json.load(f)
        stage_index = stage_info['index']
        string_path = self.project_dir / stage_info['strings']
        manifest = Manifest.load_from(string_path.parent)
        if self.version.region == Region.NTSC_J:
            return manifest.load_file(string_path.name, JapaneseStringDb, kanji_index=stage_index)
        else:
            return manifest.load_file(string_path.stem, LatinStringDb)

    @functools.cache
    def get_unmapped_strings(self) -> list[FromManifest[StringDb]]:
        """
        Get a list of unmapped strings (string databases not mapped to any stage)

        :return: A list of databases. Subsequent calls to this function always return the same list object.
        """

        mapped_strings = set()
        for stage in Stage:
            path = self.project_dir / 'stages' / stage / 'stage.json'
            with path.open('r') as f:
                stage_info = json.load(f)
            mapped_strings.add(self.project_dir / stage_info['strings'])

        messages = Manifest.try_load_from(self.project_dir / 'messages')
        if not messages:
            return []

        databases = []
        for entry in messages:
            if entry.path not in mapped_strings:
                # unmapped strings are always in Japanese
                databases.append(messages.load_file(entry.name, JapaneseStringDb))
        return databases

    @property
    def exe(self) -> Exe:
        exe_path = self.project_dir / 'boot' / self.version.exe_name
        with exe_path.open('rb') as f:
            return Exe.read(f)

    def get_stage_rooms(self, stage: Stage) -> Iterable[FromManifest[RoomModule]]:
        manifest = Manifest.load_from(self.project_dir / 'modules')
        indexes_seen = set()
        maps = self.get_maps()
        loader = functools.partial(RoomModule.load_with_metadata, version=self.version.id)
        for map_index in STAGE_MAPS[stage]:
            for room in maps[map_index].rooms:
                if room.module_index in indexes_seen:
                    continue
                yield manifest.load_file(room.module_index, loader)
                indexes_seen.add(room.module_index)

    def get_modules(self) -> Manifest:
        return Manifest.load_from(self.project_dir / 'modules')

    @functools.cache
    def get_maps(self) -> list[Map]:
        maps = self._get_maps(self.addresses['MapModules'], self.exe)
        out = []
        for i, map_ in enumerate(maps):
            rooms = [MapRoom(j, room['index'], room['entry_point']) for j, room in enumerate(map_)]
            out.append(Map(i, MAP_NAMES[i], rooms))
        return out

    def save_maps(self):
        # we expect get_maps to always return the same list of maps that's shared throughout the application
        maps = self.get_maps()
        exe_path = self.project_dir / 'boot' / self.version.exe_name
        with exe_path.open('rb') as f:
            exe = Exe.read(f)

        module_set_addr = self.addresses['MapModules']
        module_set_addrs = struct.unpack(f'<{NUM_MAPS}I',
                                         exe[module_set_addr:module_set_addr + 4 * NUM_MAPS])
        for (map_, address) in zip(maps, module_set_addrs, strict=True):
            map_bytes = map_.to_bytes()
            exe[address:address + len(map_bytes)] = map_bytes
        with exe_path.open('wb') as f:
            exe.write(f)

    def get_movie_list(self) -> list[str]:
        exe = self.exe

        num_movies = self.version.num_movies
        if self.version.region != Region.NTSC_J:
            layout = '<28s3I'
        else:
            layout = '<28s4I'
        movie_size = struct.calcsize(layout)
        address = self.addresses['Movies']
        movies = []
        for _ in range(num_movies):
            unpacked = struct.unpack(layout, exe[address:address+movie_size])
            address += movie_size
            movies.append(unpacked[0].rstrip(b'\0').decode())
        return movies

    def get_actor_models(self, usable_only: bool = False) -> Iterable[ActorModel | None]:
        is_japanese_demo = self.version.is_japanese_demo
        manifest = Manifest.load_from(self.project_dir / 'models')
        for actor in ACTORS:
            if actor.model_index is None:
                graphics = self.actor_graphics[actor.id]
                model_index = graphics.model_index
                anim_index = graphics.anim_index
            elif usable_only or is_japanese_demo:
                continue
            else:
                model_index = actor.model_index
                anim_index = None

            if model_index == 0 and is_japanese_demo:
                yield None
            else:
                model_file = manifest[model_index]
                with model_file.path.open('rb') as f:
                    yield ActorModel.read(f, actor=actor, anim_index=anim_index)

    @functools.cache
    def get_animations(self) -> Manifest:
        return Manifest.load_from(self.project_dir / 'animations')

    def get_item_art(self) -> Manifest:
        return Manifest.load_from(self.project_dir / 'art' / 'MENU').get_manifest('item_art')

    def get_art_manifests(self) -> Iterable[Manifest]:
        for path in sorted((self.project_dir / 'art').iterdir()):
            yield Manifest.load_from(path)

    def get_item_info(self) -> list[dict[str, int | None]]:
        # FIXME: we can only partially reload the info from the exe because we have no way to get back to the offsets
        #  after unpacking the TIM DB
        num_key_items = self.version.num_key_items
        addresses = self.addresses
        raw_item_art = struct.unpack(f'<{4 * num_key_items}I',
                                     self.exe[addresses['ItemArt']:addresses['ItemArt'] + 16 * num_key_items])
        item_art = [(raw_item_art[i], raw_item_art[i + 1], raw_item_art[i + 2], raw_item_art[i + 3])
                    for i in range(0, len(raw_item_art), 4)]

        json_path = self.project_dir / 'item.json'
        with json_path.open() as f:
            info = json.load(f)
        for entry in info:
            if entry['model'] is not None:
                entry['model'] = item_art[entry['id']][0]
                entry['flags'] = item_art[entry['id']][3]
        with json_path.open('w') as f:
            json.dump(info, f)
        return info

    def get_items(self, key_items: bool | None = None) -> Iterable[Item]:
        model_manifest = Manifest.load_from(self.project_dir / 'models')
        info = self.get_item_info()
        for entry in info:
            is_key_item = entry['model'] is not None
            if key_items is not None and is_key_item != key_items:
                continue
            if is_key_item:
                name = self.version.key_item_names[entry['id']]
                model_file = model_manifest[entry['model']]
                with model_file.path.open('rb') as f:
                    model = ItemModel.read(f, name=name, use_transparency=entry['flags'] & 1 == 0)
            else:
                name = MED_ITEM_NAMES[entry['id']]
                model = None
            yield Item(entry['id'], name, model, entry['description'], is_key_item)

    def get_all_models(self) -> tuple[dict[int, ActorModel], dict[int, ItemModel], dict[int, ItemModel]]:
        is_japanese_demo = self.version.is_japanese_demo
        model_manifest = Manifest.load_from(self.project_dir / 'models')
        json_path = self.project_dir / 'item.json'
        with json_path.open() as f:
            item_info = json.load(f)

        actor_models = {}
        for actor in ACTORS:
            if actor.model_index is None:
                graphics = self.actor_graphics[actor.id]
                model_index = graphics.model_index
                anim_index = graphics.anim_index
                if model_index == 0 and is_japanese_demo:
                    continue
            else:
                if is_japanese_demo:
                    continue
                model_index = actor.model_index
                anim_index = None
            if model_index not in actor_models:
                actor_models[model_index] = (actor, anim_index)

        item_models = {}
        for entry in item_info:
            if entry['model'] is not None and entry['model'] not in item_models:
                item_models[entry['model']] = (self.version.key_item_names[entry['id']], entry['flags'] & 1 == 0)

        actors = {}
        items = {}
        other = {}
        for i, model_file in enumerate(model_manifest):
            with model_file.path.open('rb') as f:
                if i in actor_models:
                    actor, anim_index = actor_models[i]
                    actors[i] = ActorModel.read(f, actor=actor, anim_index=anim_index)
                elif i in item_models:
                    name, use_transparency = item_models[i]
                    items[i] = ItemModel.read(f, name=name, use_transparency=use_transparency)
                else:
                    try:
                        other[i] = ActorModel.read(f) if model_file.format == '.G3A' else ItemModel.read(f, name=str(i))
                    except Exception:
                        # swallow exceptions for the Japanese demo as we don't have all those models working yet
                        if not is_japanese_demo:
                            raise

        return actors, items, other

    def get_menus(self) -> Iterable[tuple[str, Menu]]:
        display_manifest = Manifest.load_from(self.project_dir / 'art' / 'DISPLAY')
        # menu files only exist in Western versions
        if 'Option' in display_manifest:
            option_menu_file = display_manifest['Option']
            with option_menu_file.path.open('rb') as f:
                option_menu = Menu.read(f)
            option_menu.instantiate(self.option_menu, self.x_scales)
            yield 'Option', option_menu

        menu_manifest = Manifest.load_from(self.project_dir / 'art' / 'MENU')
        # inventory menu seems to only be in the US version
        if 'Inventory' in menu_manifest:
            inventory_menu_file = menu_manifest['Inventory']
            with inventory_menu_file.path.open('rb') as f:
                yield 'Inventory', Menu.read(f)

    @functools.cache
    def get_actor_instance_health(self) -> list[tuple[int, int]]:
        num_bytes = self.version.num_actor_instances * 4
        if self.version.region == Region.NTSC_J:
            manifest = Manifest.load_from(self.project_dir / 'modules')
            with manifest[self.version.health_module_index].path.open('rb') as f:
                f.seek(0x40)
                data = f.read()
        else:
            addresses = ADDRESSES[self.version.id]
            exe_path = self.project_dir / 'boot' / self.version.exe_name
            with exe_path.open('rb') as f:
                exe = Exe.read(f)
            address = addresses['DefaultActorInstanceHealth']
            data = exe[address:address + num_bytes]

        return [
            (file.int_from_bytes(data[i:i+2]), file.int_from_bytes(data[i+2:i+4]))
            for i in range(0, num_bytes, 4)
        ]

    @property
    def default_export_image(self) -> Path:
        return self.project_dir / 'export' / 'output.bin'

    def get_files_modified(self, mtime: float) -> tuple[list[Path], list[PurePath]]:
        """
        Get a list of project files that have been modified since the given timestamp, along with a list of the files in
        the disc image that would be modified if the project were to be exported.
        """
        input_files = []
        output_files = []

        anim_manifest = self.get_animations()
        anim_files = list(anim_manifest.get_files_modified_since(mtime))
        if anim_files:
            output_files.append(PurePath('T4/MOT.CDB'))
        input_files.extend(anim_file.path.relative_to(self.project_dir) for anim_file in anim_files)

        for art_manifest in self.get_art_manifests():
            art_files = list(art_manifest.get_files_modified_since(mtime))
            if art_files:
                output_files.append(PurePath(f'T4/{art_manifest.name}.CDB'))
            input_files.extend(art_file.path.relative_to(self.project_dir) for art_file in art_files)

        boot_dir = self.project_dir / 'boot'
        exe_path = boot_dir / self.version.exe_name
        if exe_path.stat().st_mtime > mtime:
            input_files.append(exe_path.relative_to(self.project_dir))
            if self.version.region == Region.NTSC_J:
                output_files.append(PurePath(f'T4/{exe_path.name}'))
            else:
                output_files.append(PurePath(exe_path.name))
        system_path = boot_dir / 'SYSTEM.CNF'
        if system_path.stat().st_mtime > mtime:
            input_files.append(system_path.relative_to(self.project_dir))
            output_files.append(PurePath(system_path.name))

        msg_manifest = Manifest.load_from(self.project_dir / 'messages')
        msg_files = list(msg_manifest.get_files_modified_since(mtime))
        if msg_files:
            output_files.append(PurePath(f'T4/{msg_manifest.name}.CDB'))
        input_files.extend(msg_file.path.relative_to(self.project_dir) for msg_file in msg_files)

        model_manifest = Manifest.load_from(self.project_dir / 'models')
        model_files = list(model_manifest.get_files_modified_since(mtime))
        if model_files:
            output_files.append(PurePath('T4/MODEL.CDB'))
        input_files.extend(model_file.path.relative_to(self.project_dir) for model_file in model_files)

        module_manifest = Manifest.load_from(self.project_dir / 'modules')
        module_files = list(module_manifest.get_files_modified_since(mtime))
        if module_files:
            output_files.append(PurePath('T4/MODULE.BIN'))
        input_files.extend(module_file.path.relative_to(self.project_dir) for module_file in module_files)

        sound_manifest = Manifest.load_from(self.project_dir / 'sound')
        sound_files = list(sound_manifest.get_files_modified_since(mtime))
        if sound_files:
            output_files.append(PurePath('T4/SOUND.CDB'))
        input_files.extend(sound_file.path.relative_to(self.project_dir) for sound_file in sound_files)

        for stage in Stage:
            stage: Stage

            bg_manifest = self.get_stage_backgrounds(stage)
            bg_files = list(bg_manifest.get_files_modified_since(mtime))
            if bg_files:
                output_files.append(PurePath(f'T4/BGTIM_{stage}.CDB'))
            input_files.extend(bg_file.path.relative_to(self.project_dir) for bg_file in bg_files)

            for movie in self.get_stage_movies(stage):
                if movie.path.stat().st_mtime > mtime:
                    suffix = f'_{stage}' if stage != Stage.A else ''
                    output_files.append(PurePath(f'T4/MOV{suffix}/{movie.path.name}'))
                    input_files.append(movie.path.relative_to(self.project_dir))

        voice_manifest = Manifest.load_from(self.project_dir / 'voice')
        for voice_file in voice_manifest.get_files_modified_since(mtime):
            input_files.append(voice_file.path.relative_to(self.project_dir))
            if self.version.region == Region.NTSC_J:
                output_files.append(PurePath(f'T4/XA/{voice_file.name}.BIN'))
            else:
                output_files.append(PurePath(f'T4/{voice_file.name}.MXA'))

        return input_files, output_files

    def export(self, base_image: Path, output_image: Path, mtime: float):
        patches = []

        anim_manifest = self.get_animations()
        if anim_manifest.is_modified_since(mtime):
            patches.append(Patch(r'\T4\MOT.CDB;1', anim_manifest.pack_archive(mtime)))

        for art_manifest in self.get_art_manifests():
            if art_manifest.is_modified_since(mtime):
                patches.append(Patch(rf'\T4\{art_manifest.name}.CDB;1', art_manifest.pack_archive(mtime)))

        boot_dir = self.project_dir / 'boot'
        exe_path = boot_dir / self.version.exe_name
        if exe_path.stat().st_mtime > mtime:
            data = exe_path.read_bytes()
            if self.version.region == Region.NTSC_J or self.version.is_demo:
                patches.append(Patch(rf'\T4\{exe_path.name};1', data))
            else:
                patches.append(Patch(rf'\{exe_path.name};1', data))
        system_path = boot_dir / 'SYSTEM.CNF'
        if system_path.stat().st_mtime > mtime:
            patches.append(Patch(r'\SYSTEM.CNF;1', system_path.read_bytes()))

        msg_manifest = Manifest.load_from(self.project_dir / 'messages')
        if msg_manifest.is_modified_since(mtime):
            patches.append(Patch(rf'\T4\{msg_manifest.name}.CDB;1', msg_manifest.pack_archive(mtime)))

        model_manifest = Manifest.load_from(self.project_dir / 'models')
        if model_manifest.is_modified_since(mtime):
            patches.append(Patch(r'\T4\MODEL.CDB;1', model_manifest.pack_archive(mtime)))

        module_manifest = Manifest.load_from(self.project_dir / 'modules')
        if module_manifest.is_modified_since(mtime):
            patches.append(Patch(r'\T4\MODULE.BIN;1', module_manifest.pack_archive(mtime)))

        sound_manifest = Manifest.load_from(self.project_dir / 'sound')
        if sound_manifest.is_modified_since(mtime):
            patches.append(Patch(r'\T4\SOUND.CDB;1', sound_manifest.pack_archive(mtime)))

        for stage in Stage:
            stage: Stage

            bg_manifest = self.get_stage_backgrounds(stage)
            if bg_manifest.is_modified_since(mtime):
                patches.append(Patch(rf'\T4\{bg_manifest.name}.CDB;1', bg_manifest.pack_archive(mtime)))

            for movie in self.get_stage_movies(stage):
                if movie.path.stat().st_mtime > mtime:
                    suffix = f'_{stage}' if stage != Stage.A else ''
                    patches.append(Patch(rf'\T4\MOV{suffix}\{movie.path.name};1', movie.path.read_bytes(), True))

        voice_manifest = Manifest.load_from(self.project_dir / 'voice')
        for voice_file in voice_manifest.get_files_modified_since(mtime):
            if self.version.region == Region.NTSC_J:
                patches.append(Patch(rf'\T4\XA\{voice_file.name}.BIN;1', voice_file.path.read_bytes(), True))
            else:
                patches.append(Patch(rf'\T4\{voice_file.name}.MXA;1', voice_file.path.read_bytes(), True))

        with base_image.open('rb') as f:
            cd = PsxCd(f)
        cd.patch(patches)
        # we use this temporary buffer so that, if the write were to fail, we wouldn't have already wiped the output
        # image
        with io.BytesIO() as f:
            cd.write(f)
            cd_data = f.getvalue()
        output_image.write_bytes(cd_data)

        self.last_export_date = datetime.datetime.now(datetime.UTC)
        self.save()
