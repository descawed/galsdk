from __future__ import annotations

import io
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Generic, Iterable, TypeVar

from galsdk import util
from galsdk.db import Database
from galsdk.format import Archive, FileFormat
from galsdk.sniff import sniff_file
from galsdk.tim import TimDb
from galsdk.vab import VabDb
from galsdk.xa import XaDatabase


ARCHIVE_FORMATS: dict[str, type[Archive]] = {
    'cdb': Database,
    'bin': Database,
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


T = TypeVar('T', bound=FileFormat)


@dataclass
class FromManifest(Generic[T]):
    manifest: Manifest
    key: int | str
    file: ManifestFile
    obj: T

    def save(self, **kwargs):
        with self.file.path.open('wb') as f:
            self.obj.write(f, **kwargs)


class Manifest:
    """A manifest records an ordered list of files that belong to an archive"""

    files: list[ManifestFile]

    def __init__(self, path: Path, name: str = None, db_type: str | None = 'cdb', original: Path = None,
                 metadata: dict[str, bool | int | float | str | list | tuple | dict] = None):
        """
        Create a new empty manifest at the given path with the given name

        :param path: Path where the manifest and its files will be stored
        :param name: Name of the archive the manifest originates from
        """
        self.path = path
        self.path.mkdir(exist_ok=True)
        self.original = original
        self.name = name
        self.files = []
        self.name_map = {}
        self.type = db_type
        self.metadata = metadata or {}

    def _unpack_file(self, mf: ManifestFile, parent: Archive, i: int, sniff: bool | list[type[FileFormat]],
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

    def unpack_archive(self, archive: Archive, extension: str = '', sniff: bool | list[type[FileFormat]] = False,
                       flatten: bool = False, recursive: bool = True, original_path: Path = None):
        if extension and extension[0] != '.':
            extension = '.' + extension
        self.type = archive.suggested_extension[1:].lower()
        self.metadata = archive.metadata
        save_path = self.path / 'original.bin'
        if original_path is not None:
            shutil.copy(original_path, save_path)
        elif raw_data := archive.raw_data:
            save_path.write_bytes(raw_data)
        else:
            save_path = None
        self.original = save_path
        for i, entry in enumerate(archive):
            name = f'{i:03}'
            filename = f'{name}{extension}'
            file_path = self.path / filename
            util.unlink(file_path)
            mf = ManifestFile(name, file_path)
            self.files.append(mf)
            self.name_map[mf.name] = mf
            self._unpack_file(mf, archive, i, sniff, flatten, recursive)

    def pack_archive(self, mtime: float = 0.) -> bytes:
        if not self.is_modified_since(mtime) and self.original:
            # nothing has changed, we can just serve the original file
            return self.original.read_bytes()

        archive = ARCHIVE_FORMATS[self.type].from_metadata(self.metadata)
        for mf in self.files:
            if mf.is_manifest:
                sub_manifest = Manifest.load_from(mf.path)
                data = sub_manifest.pack_archive(mtime)
            else:
                data = mf.path.read_bytes()
            archive.append_raw(data)

        if not self.original:
            self.original = self.path / 'original.bin'
            self.save()

        # we use r+b because we want the original file to be overwritten in place, leaving any extra bytes at the end of
        # the file or the ends of headers. that will minimize the diff with the original file.
        with self.original.open('r+b') as f:
            archive.write(f)
            # TODO: should we truncate here? might be necessary for stream formats
        return self.original.read_bytes()

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
        self.metadata = manifest['metadata']
        self.original = (self.path / manifest['original']) if manifest['original'] else None

    def load_file(self, key: int | str, constructor: type[T] | Callable[[Path], T], **kwargs) -> FromManifest[T]:
        """
        Create a FileFormat instance of the given type from the file identified by key, returning a FromManifest
        instance that tracks the file and manifest the object originated from.
        """
        manifest_file = self[key]
        if isinstance(constructor, type) and issubclass(constructor, FileFormat):
            with manifest_file.path.open('rb') as f:
                obj = constructor.read(f, **kwargs)
        else:
            obj = constructor(manifest_file.path)
        return FromManifest(self, key, manifest_file, obj)

    def save(self):
        """Save the current file data for this manifest"""
        with (self.path / 'manifest.json').open('w') as f:
            json.dump({
                'name': self.name,
                'files': [{'name': mf.name, 'path': mf.path.name, 'format': mf.format} for mf in self.files],
                'type': self.type,
                'metadata': self.metadata,
                'original': str(self.original.relative_to(self.path)) if self.original is not None else None,
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

    def get_files_modified_since(self, mtime: float) -> Iterable[ManifestFile]:
        for mf in self.files:
            if mf.is_manifest:
                sub_manifest = Manifest.load_from(mf.path)
                yield from sub_manifest.get_files_modified_since(mtime)
            else:
                if mf.path.stat().st_mtime > mtime:
                    yield mf

    def is_modified_since(self, mtime: float) -> bool:
        for _ in self.get_files_modified_since(mtime):
            return True
        return False

    def rename(self, key: int | str, name: str, on_disk: bool = True, ext: str = None):
        """Rename a file in the manifest by index or name"""
        mf = self.files[key] if isinstance(key, int) else self.name_map[key]
        if name != mf.name:
            if name in self.name_map:
                raise KeyError(f'There is already an entry named {name}')
            if on_disk:
                new_path = mf.path.with_stem(name)
                if ext is not None:
                    new_path = new_path.with_suffix(ext)
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
                     sniff: bool | list[type[FileFormat]] = False, flatten: bool = False,
                     recursive: bool = True, original_path: Path = None) -> Manifest:
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
        :param original_path: The path to the original file the archive was read from, which will be copied and saved
        :return: The new manifest
        """
        manifest = cls(manifest_path, name)
        manifest.unpack_archive(archive, extension, sniff, flatten, recursive, original_path)
        manifest.save()
        return manifest

    @classmethod
    def from_directory(cls, manifest_path: Path, name: str):
        manifest = cls(manifest_path, name, None)
        for path in sorted(manifest_path.iterdir()):
            if not path.is_file() or path.name == 'manifest.json':
                continue
            mf = ManifestFile(path.stem, path)
            manifest.files.append(mf)
            manifest.name_map[path.stem] = mf
        manifest.save()
        return manifest
