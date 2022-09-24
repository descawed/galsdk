from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterable

from galsdk.db import Database


@dataclass
class ManifestFile:
    name: str
    path: Path


class Manifest:
    """A manifest records an ordered list of files that belong to a database"""

    def __init__(self, path: Path, name: str = None):
        """
        Create a new empty manifest at the given path with the given name

        :param path: Path where the manifest and its files will be stored
        :param name: Name of the database the manifest originates from
        """
        self.path = path
        self.name = name
        self.files = []
        self.name_map = {}

    def unpack_database(self, db: Database, extension: str = None):
        """
        Unpack the given database to the manifest directory and record its files in the manifest

        :param db: Database to unpack
        :param extension: If not None, the unpacked files will have this extension added
        """
        files = []
        ext = f'.{extension}' if extension is not None else ''
        for i, entry in enumerate(db):
            name = f'{i:03X}'
            filename = f'{name}{ext}'
            files.append({'name': name, 'path': filename})
            file_path = self.path / filename
            mf = ManifestFile(name, file_path)
            self.files.append(mf)
            self.name_map[name] = mf
            with file_path.open('wb') as f:
                f.write(entry)
        with (self.path / 'manifest.json').open('w') as f:
            json.dump({'name': self.name, 'files': files}, f)

    def load(self):
        """Load the last saved manifest data for this path"""
        with (self.path / 'manifest.json').open() as f:
            manifest = json.load(f)
        self.name = manifest['name']
        self.files = [ManifestFile(entry['name'], self.path / entry['path']) for entry in manifest['files']]
        self.name_map = {mf.name: mf for mf in self.files}

    def save(self):
        """Save the current file data for this manifest"""
        with (self.path / 'manifest.json').open('w') as f:
            json.dump({
                'name': self.name,
                'files': [{'name': mf.name, 'path': mf.path.name} for mf in self.files]
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

    def rename(self, key: int | str, name: str):
        """Rename a file in the manifest by index or name"""
        mf = self.files[key] if isinstance(key, int) else self.name_map[key]
        if name != mf.name:
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
        manifest = cls(manifest_path, db_path.stem)
        db = Database()
        with db_path.open('rb') as f:
            db.read(f)
        manifest.unpack_database(db, extension)
        return manifest
