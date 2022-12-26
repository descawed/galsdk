from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import BinaryIO, Iterable

from galsdk.db import Database
from galsdk.tim import TimDb
from galsdk.vab import VabDb
from galsdk.xa import XaDatabase


class DatabaseType(str, Enum):
    CDB = 'cdb'
    CDB_EXT = 'cdb_ext'
    TIM = 'tim'
    VAB = 'vab'
    VAB_ALT = 'vab_alt'
    XA = 'xa'

    def __str__(self):
        return self.value


@dataclass
class ManifestFile:
    name: str
    path: Path


class Manifest:
    """A manifest records an ordered list of files that belong to a database"""

    files: list[ManifestFile]

    def __init__(self, path: Path, name: str = None, db_type: DatabaseType = DatabaseType.CDB):
        """
        Create a new empty manifest at the given path with the given name

        :param path: Path where the manifest and its files will be stored
        :param name: Name of the database the manifest originates from
        """
        self.path = path
        self.name = name
        self.files = []
        self.name_map = {}
        self.type = db_type

    def _unpack_generic_database(self, db: Iterable[bytes], extension: str = None):
        ext = f'.{extension}' if extension is not None else ''
        for i, entry in enumerate(db):
            name = f'{i:03X}'
            filename = f'{name}{ext}'
            file_path = self.path / filename
            mf = ManifestFile(name, file_path)
            self.files.append(mf)
            self.name_map[name] = mf
            with file_path.open('wb') as f:
                f.write(entry)
        self.save()

    def unpack_database(self, db: Database, extension: str = None):
        """
        Unpack the given database to the manifest directory and record its files in the manifest

        :param db: Database to unpack
        :param extension: If not None, the unpacked files will have this extension added
        """
        self._unpack_generic_database(db, extension)

    def unpack_tim_database(self, db: TimDb):
        for i, entry in enumerate(db):
            name = f'{i:03X}'
            filename = f'{name}.TIM'
            file_path = self.path / filename
            mf = ManifestFile(name, file_path)
            self.files.append(mf)
            self.name_map[name] = mf
            with file_path.open('wb') as f:
                entry.write(f)
        self.save()

    def unpack_vab_database(self, db: VabDb):
        for ext, entries in db.files_with_type:
            for i, entry in enumerate(entries):
                name = f'{i:03X}.{ext}'
                file_path = self.path / name
                mf = ManifestFile(name, file_path)
                self.files.append(mf)
                self.name_map[name] = mf
                with file_path.open('wb') as f:
                    f.write(entry)
        self.save()

    def unpack_xa_database(self, db: XaDatabase):
        self._unpack_generic_database(db, 'XA')

    def load(self):
        """Load the last saved manifest data for this path"""
        with (self.path / 'manifest.json').open() as f:
            manifest = json.load(f)
        self.name = manifest['name']
        self.files = [ManifestFile(entry['name'], self.path / entry['path']) for entry in manifest['files']]
        self.name_map = {mf.name: mf for mf in self.files}
        self.type = DatabaseType(manifest['type'])

    def save(self):
        """Save the current file data for this manifest"""
        with (self.path / 'manifest.json').open('w') as f:
            json.dump({
                'name': self.name,
                'files': [{'name': mf.name, 'path': mf.path.name} for mf in self.files],
                'type': self.type,
            }, f)

    def __getitem__(self, item: int | str) -> ManifestFile:
        """Retrieve an item from the manifest by index or name"""
        return self.files[item] if isinstance(item, int) else self.name_map[item]

    def __iter__(self) -> Iterable[ManifestFile]:
        """Iterate over the files in the manifest"""
        yield from self.files

    def __len__(self) -> int:
        """Number of files in the manifest"""
        return len(self.files)

    def rename(self, key: int | str, name: str, on_disk: bool = True):
        """Rename a file in the manifest by index or name"""
        mf = self.files[key] if isinstance(key, int) else self.name_map[key]
        if name != mf.name:
            if on_disk:
                new_path = mf.path.with_stem(name)
                new_path.unlink(True)
                mf.path = mf.path.rename(new_path)
            if name in self.name_map:
                raise KeyError(f'There is already an entry named {name}')
            del self.name_map[mf.name]
            mf.name = name
            self.name_map[name] = mf

    @classmethod
    def load_from(cls, path: Path) -> Manifest:
        """
        Load a manifest from a given path

        :param path: Path where the manifest is stored
        :return: The manifest object
        """
        manifest = cls(path)
        manifest.load()
        return manifest

    @classmethod
    def from_database(cls, manifest_path: Path, db_path: Path, extension: str = None) -> Manifest:
        """
        Create a new manifest at a given path from a database at a given path

        :param manifest_path: Path to the directory to hold the manifest and its contents
        :param db_path: Path to the database file to be unpacked
        :param extension: If not None, a file extension to use for the files unpacked from the database
        :return: The new manifest
        """
        db = Database()
        with db_path.open('rb') as f:
            db.read(f)
        manifest = cls(manifest_path, db_path.stem, DatabaseType.CDB_EXT if db.extended else DatabaseType.CDB)
        manifest.unpack_database(db, extension)
        return manifest

    @classmethod
    def from_tim_database(cls, manifest_path: Path, db_path: Path, compressed: bool = False) -> Manifest:
        manifest = cls(manifest_path, db_path.stem, DatabaseType.TIM)
        db = TimDb()
        with db_path.open('rb') as f:
            db.read(f, compressed)
        manifest.unpack_tim_database(db)
        return manifest

    @classmethod
    def from_vab_database(cls, manifest_path: Path, db_path: Path) -> Manifest:
        with db_path.open('rb') as f:
            db = VabDb.read(f)
        manifest = cls(manifest_path, db_path.stem, DatabaseType.VAB_ALT if db.use_alt_order else DatabaseType.VAB)
        manifest.unpack_vab_database(db)
        return manifest

    @classmethod
    def from_xa_database(cls, manifest_path: Path, db_map: BinaryIO, db_data: Path) -> Manifest:
        db = XaDatabase.read(db_map)
        with db_data.open('rb') as f:
            db.set_data(f.read())
        manifest = cls(manifest_path, db_data.stem, DatabaseType.XA)
        manifest.unpack_xa_database(db)
        return manifest
