from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Type

from galsdk import util
from galsdk.db import Database
from galsdk.format import Archive, FileFormat
from galsdk.sniff import sniff_file
from galsdk.tim import TimDb
from galsdk.vab import VabDb
from galsdk.xa import XaDatabase


ARCHIVE_FORMATS: dict[str, Type[Archive]] = {
    'cdb': Database,
    'tda': TimDb,
    'tdb': TimDb,
    'tdc': TimDb,
    'tmc': TimDb,
    'vda': VabDb,
    'vdb': VabDb,
    'xdb': XaDatabase,
}


@dataclass
class ManifestFile:
    name: str
    path: Path
    is_manifest: bool = False
    format: str = None


class Manifest:
    """A manifest records an ordered list of files that belong to an archive"""

    files: list[ManifestFile]

    def __init__(self, path: Path, name: str = None, db_type: str = 'cdb'):
        """
        Create a new empty manifest at the given path with the given name

        :param path: Path where the manifest and its files will be stored
        :param name: Name of the archive the manifest originates from
        """
        self.path = path
        self.path.mkdir(exist_ok=True)
        self.name = name
        self.files = []
        self.name_map = {}
        self.type = db_type

    def _unpack_file(self, mf: ManifestFile, parent: Archive, i: int, sniff: bool | list[Type[FileFormat]],
                     flatten: bool, recursive: bool):
        entry = parent[i]
        if not isinstance(entry, Archive) or not recursive:
            mf.path = parent.unpack_one(mf.path, i)

            detected_format = None
            if sniff:
                if isinstance(entry, FileFormat):
                    detected_format = entry
                else:
                    formats = None if isinstance(sniff, bool) else sniff
                    detected_format = sniff_file(mf.path, formats)

            if detected_format:
                mf.format = detected_format.suggested_extension
                new_path = mf.path.with_suffix(detected_format.suggested_extension)
                if new_path != mf.path:
                    util.unlink(new_path)
                if recursive and isinstance(detected_format, Archive) and detected_format.is_ready:
                    util.unlink(mf.path)
                    mf.path = new_path
                    archive = detected_format
                else:
                    if new_path != mf.path and mf.path.suffix == '':  # don't change the extension if it already had one
                        mf.path = mf.path.rename(new_path)
                    return
            else:
                return
        else:
            archive = entry

        if flatten and len(archive) == 1:
            self._unpack_file(mf, archive, 0, sniff, flatten, False)
        else:
            Manifest.from_archive(mf.path, f'{self.name}_{mf.name}', archive, sniff=sniff, flatten=flatten)
            mf.is_manifest = True

    def unpack_archive(self, archive: Archive, extension: str = '', sniff: bool | list[Type[FileFormat]] = False,
                       flatten: bool = False, recursive: bool = True):
        if extension and extension[0] != '.':
            extension = '.' + extension
        self.type = archive.suggested_extension[1:].lower()
        for i, entry in enumerate(archive):
            name = f'{i:03}'
            filename = f'{name}{extension}'
            file_path = self.path / filename
            util.unlink(file_path)
            mf = ManifestFile(name, file_path)
            self.files.append(mf)
            self.name_map[mf.name] = mf
            self._unpack_file(mf, archive, i, sniff, flatten, recursive)

    def load(self):
        """Load the last saved manifest data for this path"""
        with (self.path / 'manifest.json').open() as f:
            manifest = json.load(f)
        self.name = manifest['name']
        self.files = []
        for entry in manifest['files']:
            path = self.path / entry['path']
            self.files.append(ManifestFile(entry['name'], path, (path / 'manifest.json').exists(), entry['format']))
        self.name_map = {mf.name: mf for mf in self.files}
        self.type = manifest['type']

    def save(self):
        """Save the current file data for this manifest"""
        with (self.path / 'manifest.json').open('w') as f:
            json.dump({
                'name': self.name,
                'files': [{'name': mf.name, 'path': mf.path.name, 'format': mf.format} for mf in self.files],
                'type': self.type,
            }, f)

    def __getitem__(self, item: int | str) -> ManifestFile:
        """Retrieve an item from the manifest by index or name"""
        if isinstance(item, str):
            pieces = item.split('/', 1)
            mf = self.name_map[pieces[0]]
            if mf.is_manifest and len(pieces) > 1:
                sub_manifest = Manifest.load_from(mf.path)
                return sub_manifest[pieces[1]]
            else:
                return mf
        else:
            return self.files[item]

    def __iter__(self) -> Iterable[ManifestFile]:
        """Iterate over the files in the manifest"""
        yield from self.files

    def __len__(self) -> int:
        """Number of files in the manifest"""
        return len(self.files)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.save()

    def iter_flat(self) -> Iterable[ManifestFile]:
        for item in self.files:
            if item.is_manifest:
                sub_manifest = Manifest.load_from(item.path)
                yield from sub_manifest.iter_flat()
            else:
                yield item

    def get_first(self, key: int | str) -> ManifestFile:
        """Get the file with the given key. If the file is a manifest, get the first file in it recursively."""
        mf = self[key]
        if not mf.is_manifest:
            return mf

        sub_manifest = Manifest.load_from(mf.path)
        return sub_manifest.get_first(0)

    def get_manifest(self, key: int | str) -> Manifest:
        mf = self[key]
        if not mf.is_manifest:
            raise TypeError('The given key does not correspond to a manifest')
        return Manifest.load_from(mf.path)

    def rename(self, key: int | str, name: str, on_disk: bool = True):
        """Rename a file in the manifest by index or name"""
        mf = self.files[key] if isinstance(key, int) else self.name_map[key]
        if name != mf.name:
            if name in self.name_map:
                raise KeyError(f'There is already an entry named {name}')
            if on_disk:
                new_path = mf.path.with_stem(name)
                util.unlink(new_path)
                mf.path = mf.path.rename(new_path)
                if mf.is_manifest:
                    sub_manifest = Manifest.load_from(mf.path)
                    sub_manifest.name = name
                    sub_manifest.save()
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
    def try_load_from(cls, path: Path) -> Manifest | None:
        """
        Try to load a manifest from a given path

        :param path: Path where the manifest is stored
        :return: The manifest object or None
        """
        try:
            return cls.load_from(path)
        except (FileNotFoundError, KeyError, json.JSONDecodeError):
            return None

    @classmethod
    def from_archive(cls, manifest_path: Path, name: str, archive: Archive, extension: str = '',
                     sniff: bool | list[Type[FileFormat]] = False, flatten: bool = False,
                     recursive: bool = True) -> Manifest:
        """
        Create a new manifest at a given path from a given archive

        :param manifest_path: Path to the directory to hold the manifest and its contents
        :param name: The name to identify this manifest by
        :param archive: The archive to be unpacked
        :param extension: If not None, a file extension to use for the files unpacked from the archive. This extension
            is advisory and the archive may choose to use its own.
        :param sniff: Attempt to automatically detect the format of files that the archive does not know the format of.
            If any files are detected to be archives themselves, they will be unpacked recursively if the recursive
            parameter is true.
        :param flatten: When recursively unpacking, do not make sub-manifests for archives with a single entry.
        :param recursive: If the archive contains nested archives, unpack them recursively
        :return: The new manifest
        """
        manifest = cls(manifest_path, name)
        manifest.unpack_archive(archive, extension, sniff, flatten, recursive)
        manifest.save()
        return manifest
