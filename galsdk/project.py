from __future__ import annotations

import datetime
import json
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

from psx.cd import PsxCd


class Region(str, Enum):
    NTSC_U = 'NTSC-U'
    NTSC_J = 'NTSC-J'
    PAL = 'PAL'


@dataclass
class GameVersion:
    """Information on the specific version of the game this project was created from and will be exported as"""

    region: Region
    language: str
    disc: int
    is_demo: bool = False


VERSION_MAP = {
    'SLUS-00986': GameVersion(Region.NTSC_U, 'en-US', 1),
    'SLUS-01098': GameVersion(Region.NTSC_U, 'en-US', 2),
    'SLUS-01099': GameVersion(Region.NTSC_U, 'en-US', 3),

    'SLUS-90077': GameVersion(Region.NTSC_U, 'en-US', 1, True),

    'SLPS-02192': GameVersion(Region.NTSC_J, 'ja', 1),
    'SLPS-02193': GameVersion(Region.NTSC_J, 'ja', 2),
    'SLPS-02194': GameVersion(Region.NTSC_J, 'ja', 3),

    'SLES-02328': GameVersion(Region.PAL, 'en-GB', 1),
    'SLES-12328': GameVersion(Region.PAL, 'en-GB', 2),
    'SLES-22328': GameVersion(Region.PAL, 'en-GB', 3),

    'SLES-02329': GameVersion(Region.PAL, 'fr', 1),
    'SLES-12329': GameVersion(Region.PAL, 'fr', 2),
    'SLES-22329': GameVersion(Region.PAL, 'fr', 3),

    'SLES-02330': GameVersion(Region.PAL, 'de', 1),
    'SLES-12330': GameVersion(Region.PAL, 'de', 2),
    'SLES-22330': GameVersion(Region.PAL, 'de', 3),
}


class Project:
    """
    Container for the data and metadata of the game being edited

    The Project contains information about the game files being edited, the game version, and various editor metadata
    that isn't stored in the game's own data files. It also provides a version-agnostic interface for manipulating game
    objects and CD images.
    """
    def __init__(self, project_dir: Path, version: GameVersion, last_export_date: datetime.datetime = None):
        self.project_dir = project_dir
        self.version = version
        self.last_export_date = last_export_date or datetime.datetime.utcnow()

    @classmethod
    def _extract_dir(cls, path: str, destination: Path, cd: PsxCd, raw: bool = False):
        for entry in cd.list_dir(path):
            sub_path = destination / entry.name
            if entry.is_directory:
                sub_path.mkdir(exist_ok=True)
                # raw extraction if this is the XA directory in the Japanese version or a movie directory in any version
                cls._extract_dir(entry.path, sub_path, cd, entry.name == 'XA' or entry.name.startswith('MOV'))
            else:
                with sub_path.open('wb') as f:
                    # raw extraction if requested for the dir or if this is the XA archive in the NA version
                    cd.extract(entry.path, f, raw or entry.name == 'XA.MXA')

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
            cls._extract_dir('\\', Path(d.name), cd)
            return cls.create_from_directory(d.name, cd_path, project_dir)

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
        config = (game_path / 'SYSTEM.CNF').read_text()
        boot_to_game_id = re.compile(r'^BOOT\s*=.+S([a-z]{3})_(\d{3})\.(\d{2});\d+$', re.IGNORECASE)
        for line in config.splitlines():
            game_id, matches = boot_to_game_id.subn(r'S\1-\2\3', line)
            if matches > 0:
                version = VERSION_MAP[game_id]
                break
        else:
            raise ValueError('Could not determine game version from SYSTEM.CNF')

        if version.region != Region.NTSC_U or version.is_demo:
            raise NotImplementedError('Currently only the US retail version of the game is supported')

        # locate files we're interested in
        game_data = game_path / 'T4'
        display_db = game_data / 'DISPLAY.CDB'
        model_db = game_data / 'MODEL.CDB'

        # prepare project directory
        export_dir = project_path / 'export'
        export_dir.mkdir(exist_ok=True)
        shutil.copy(base_image, export_dir / 'output.bin')
        shutil.copy(display_db, export_dir)
        shutil.copy(model_db, export_dir)

        stages_dir = project_path / 'stages'
        stages_dir.mkdir(exist_ok=True)
        for stage in ['A', 'B', 'C', 'D']:
            stage_dir = stages_dir / stage
            stage_dir.mkdir(exist_ok=True)
            bg_dir = stage_dir / 'backgrounds'
            bg_dir.mkdir(exist_ok=True)
            movie_dir = stage_dir / 'movies'
            movie_dir.mkdir(exist_ok=True)

            movie_src = game_data / 'MOV' if stage == 'A' else f'MOV_{stage}'
            # depending on which disc we're on, some of these directories won't exist
            if movie_src.exists():
                shutil.copytree(movie_src, movie_dir)

            # TODO: extract backgrounds
            # TODO: extract strings

        actor_dir = project_path / 'actors'
        actor_dir.mkdir(exist_ok=True)

        # TODO: extract actor models

        room_dir = project_path / 'rooms'
        room_dir.mkdir(exist_ok=True)

        # TODO: extract room data

        sound_dir = project_path / 'sound'
        sound_dir.mkdir(exist_ok=True)

        # TODO: extract sound database

        voice_dir = project_path / 'voice'
        voice_dir.mkdir(exist_ok=True)

        # TODO: extract XA audio

        project = cls(project_path, version)
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
        return Project(project_path, version, last_export_date)

    def save(self):
        """Save project metadata"""
        with (self.project_dir / 'project.json').open('w') as f:
            json.dump({
                'version': asdict(self.version),
                'last_export_date': self.last_export_date.isoformat(),
            }, f)
