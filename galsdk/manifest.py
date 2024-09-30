from __future__ import annotations

import bisect
import datetime
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable
from weakref import WeakValueDictionary

from galsdk import file
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
    flatten: bool = False

    @property
    def ext_name(self) -> str:
        name = self.name
        if self.format:
            if self.format[0] != '.':
                name += '.'
            name += self.format
        return name

    @property
    def manifest(self) -> Manifest:
        if not self.is_manifest:
            raise AttributeError(f'Manifest file {self.name} is not a manifest')
        return Manifest.load_from(self.path)


@dataclass
class Delete:
    file: ManifestFile
    timestamp: float
    index: int


@dataclass
class Rename:
    file: ManifestFile
    old_name: str
    rename_file: bool
    ext: str = None
    manifest: Manifest = None


@dataclass
class AddFile:
    file: ManifestFile
    undelete: tuple[float, ManifestFile] | None


@dataclass
class AddManifest:
    file: ManifestFile
    manifest: Manifest
    undelete: tuple[float, ManifestFile] | None


type ManifestChange = Delete | Rename | AddFile | AddManifest
type JsonType = bool | int | float | str | list | tuple | dict | None


@dataclass
class FromManifest[T: FileFormat]:
    manifest: Manifest
    key: int | str
    file: ManifestFile
    obj: T

    def save(self, **kwargs):
        with self.file.path.open('wb') as f:
            self.obj.write(f, **kwargs)


class Manifest:
    """A manifest records an ordered list of files that belong to an archive"""

    _loaded_manifests: WeakValueDictionary[Path, Manifest] = WeakValueDictionary()

    files: list[ManifestFile]
    name_map: dict[str, ManifestFile]
    deleted_files: list[tuple[float, ManifestFile]]
    pending_changes: list[ManifestChange]

    def __new__(cls, path: Path, *args, **kwargs):
        if (instance := cls._loaded_manifests.get(path)) is not None:
            return instance

        instance = super().__new__(cls)
        cls._loaded_manifests[path] = instance
        return instance

    def __init__(self, path: Path, name: str = None, db_type: str | None = 'cdb', original: Path = None,
                 metadata: dict[str, JsonType] = None):
        """
        Create a new empty manifest at the given path with the given name

        :param path: Path where the manifest and its files will be stored. Note that the manifest expects to have
                     exclusive ownership of this directory. Files or directories placed here that are not part of the
                     manifest may be deleted or overwritten at any time.
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
        self.deleted_files = []
        self.pending_changes = []
        self.is_deleted = False

    def __del__(self):
        self.undo()

    @staticmethod
    def now() -> float:
        return datetime.datetime.now(datetime.UTC).timestamp()

    def _unpack_file(self, mf: ManifestFile, parent: Archive, i: int, sniff: bool | list[type[FileFormat]],
                     flatten: bool, recursive: bool):
        entry = parent[i]
        if not isinstance(entry, Archive) or not recursive:
            mf.path = parent.unpack_one(mf.path, i)

            detected_format = None
            if isinstance(entry, FileFormat):
                detected_format = entry
            elif sniff:
                formats = None if isinstance(sniff, bool) else sniff
                detected_format = sniff_file(mf.path, formats)

            if detected_format:
                mf.format = detected_format.suggested_extension
                new_path = mf.path.with_suffix(detected_format.suggested_extension)
                if new_path != mf.path:
                    file.unlink(new_path)
                if recursive and isinstance(detected_format, Archive) and detected_format.is_ready:
                    file.unlink(mf.path)
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
            manifest = Manifest.from_archive(mf.path, f'{self.name}_{mf.name}', archive, sniff=sniff, flatten=flatten)
            mf.is_manifest = True
            if archive.should_flatten:
                mf.flatten = True
                # push this filename down to the flattened file
                with manifest:
                    manifest.rename(0, mf.name, False)

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
            file.unlink(file_path)
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

        if self.original.exists():
            # we use r+b because we want the original file to be overwritten in place, leaving any extra bytes at the
            # end of the file or the ends of headers. that will minimize the diff with the original file.
            f = self.original.open('r+b')
        else:
            f = self.original.open('wb')
        with f:
            archive.write(f)
            # TODO: should we truncate here? might be necessary for stream formats
        return self.original.read_bytes()

    def _update_path(self, new_path: Path):
        if self.path == new_path:
            return

        # assumes that we've already been moved to the new path
        old_path = self.path
        self.path = new_path
        if old_path in self._loaded_manifests:
            del self._loaded_manifests[old_path]
            self._loaded_manifests[self.path] = self

        if self.original:
            original_relative_path = self.original.relative_to(old_path)
            self.original = self.path / original_relative_path

        for mf in self.files:
            file_old_path = mf.path
            relative_path = mf.path.relative_to(old_path)
            mf.path = self.path / relative_path
            if mf.is_manifest:
                # if the manifest is currently loaded under the old path, we want that instance. otherwise, load it
                # fresh.
                if (sub_manifest := self.get_if_loaded(file_old_path)) is None:
                    sub_manifest = Manifest.load_from(mf.path)
                sub_manifest._update_path(mf.path)

    def load(self):
        """Load the last saved manifest data for this path"""
        with (self.path / 'manifest.json').open() as f:
            manifest = json.load(f)
        self.name = manifest['name']
        self.files = []
        for entry in manifest['files']:
            path = self.path / entry['path']
            self.files.append(ManifestFile(entry['name'], path, (path / 'manifest.json').exists(), entry['format'],
                                           entry.get('flatten', False)))
        self.name_map = {mf.name: mf for mf in self.files}
        self.type = manifest['type']
        self.metadata = manifest['metadata']
        self.original = (self.path / manifest['original']) if manifest['original'] else None
        deletions = manifest.get('deletions', [])
        self.deleted_files = []
        for deletion in deletions:
            self.deleted_files.append(
                (deletion['timestamp'], ManifestFile(deletion['name'], self.path / deletion['path']))
            )

    def load_file[T](self, key: int | str, constructor: type[T] | Callable[[Path], T], **kwargs) -> FromManifest[T]:
        """
        Create a FileFormat instance of the given type from the file identified by key, returning a FromManifest
        instance that tracks the file and manifest the object originated from.
        """
        manifest_file = self.expand_file(self[key])
        if isinstance(constructor, type) and issubclass(constructor, FileFormat):
            with manifest_file.path.open('rb') as f:
                obj = constructor.read(f, **kwargs)
        else:
            obj = constructor(manifest_file.path)
        return FromManifest(self, key, manifest_file, obj)

    def load_files[T](self, constructor: type[T] | Callable[[Path], T], **kwargs) -> Iterable[FromManifest[T]]:
        for i, mf in enumerate(self.files):
            if not mf.is_manifest or mf.flatten:
                yield self.load_file(i, constructor, **kwargs)

    def save(self):
        """Save the current file data for this manifest"""
        added_files = set()
        for change in self.pending_changes:
            match change:
                case Delete(mf, timestamp):
                    if mf.is_manifest:
                        mf.manifest.delete()
                    else:
                        mf.path.unlink()
                    # don't add a file to the deleted list if it hasn't been saved
                    if mf.name in added_files:
                        added_files.remove(mf.name)
                    else:
                        self.deleted_files.append((timestamp, mf))
                case Rename(mf, _, rename_file, ext, sub_manifest):
                    sub_manifest: Manifest | None
                    if rename_file:
                        new_path = mf.path.with_stem(mf.name)
                        if ext is not None:
                            new_path = new_path.with_suffix(ext)
                        file.unlink(new_path)
                        mf.path = mf.path.rename(new_path)
                        if sub_manifest is not None:
                            sub_manifest._update_path(mf.path)
                            sub_manifest.save()
                case AddFile(mf) | AddManifest(mf):
                    if self.try_undelete(mf.name) is None:
                        added_files.add(mf.name)
        self.pending_changes = []

        with (self.path / 'manifest.json').open('w') as f:
            json.dump({
                'name': self.name,
                'files': [
                    {'name': mf.name, 'path': mf.path.name, 'format': mf.format, 'flatten': mf.flatten}
                    for mf in self.files
                ],
                'type': self.type,
                'metadata': self.metadata,
                'deletions': [
                    {'timestamp': mtime, 'name': mf.name, 'path': str(mf.path.relative_to(self.path))}
                    for mtime, mf in self.deleted_files
                ],
                'original': str(self.original.relative_to(self.path)) if self.original is not None else None,
            }, f)

    def undo(self, num_changes: int = None):
        if num_changes is None:
            num_changes = len(self.pending_changes)

        while num_changes > 0:
            change = self.pending_changes.pop()
            match change:
                case Delete(mf, _, index):
                    # we don't remove from deleted_files because we don't insert until save
                    self.files.insert(index, mf)
                    self.name_map[mf.name] = mf
                case Rename(mf, old_name, manifest=sub_manifest):
                    del self.name_map[mf.name]
                    self.name_map[old_name] = mf
                    mf.name = old_name
                    if sub_manifest is not None:
                        sub_manifest.name = old_name
                        if mf.flatten:
                            # a flattened manifest should never be exposed outside of its containing manifest, so we can
                            # be confident that we're the only one that's been making changes to it.
                            sub_manifest.undo(1)
                case AddFile(mf, undelete):
                    del self.name_map[mf.name]
                    self.files.remove(mf)
                    mf.path.unlink()
                    if undelete:
                        self.deleted_files.append(undelete)
                case AddManifest(mf, manifest, undelete):
                    del self.name_map[mf.name]
                    self.files.remove(mf)
                    manifest.delete()
                    if undelete:
                        self.deleted_files.append(undelete)
            num_changes -= 1

    def delete(self):
        shutil.rmtree(self.path)
        self.original = None
        self.files = []
        self.name_map = {}
        self.type = None
        self.metadata = {}
        self.deleted_files = []
        self.pending_changes = []
        self.is_deleted = True

    @classmethod
    def expand_file(cls, mf: ManifestFile) -> ManifestFile:
        if mf.is_manifest and mf.flatten:
            sub_manifest = Manifest.load_from(mf.path)
            return cls.expand_file(sub_manifest[0])
        return mf

    def __getitem__(self, item: int | str) -> ManifestFile:
        """Retrieve an item from the manifest by index or name"""
        if isinstance(item, str):
            mf = self.name_map[item]
            return self.expand_file(mf)
        else:
            return self.expand_file(self.files[item])

    def __delitem__(self, key: int | str):
        """Remove an item from the manifest by index or name"""
        if isinstance(key, str):
            mf = self.name_map[key]
            index = self.files.index(mf)
            del self.files[index]
        else:
            index = key
            mf = self.files[key]
            del self.files[key]

        del self.name_map[mf.name]
        self.pending_changes.append(Delete(mf, self.now(), index))

    def __contains__(self, item: int | str) -> bool:
        """Check if a given index or name exists in the manifest"""
        if isinstance(item, str):
            return item in self.name_map
        elif item < 0:
            return item >= -len(self.files)
        else:
            return item < len(self.files)

    def __iter__(self) -> Iterable[ManifestFile]:
        """Iterate over the files in the manifest"""
        for mf in self.files:
            if mf.is_manifest and mf.flatten:
                yield from mf.manifest
            else:
                yield mf

    def __len__(self) -> int:
        """Number of files in the manifest"""
        return len(self.files)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.save()

    def get_unique_name(self, name: str, check_path: bool = False) -> str:
        i = 0
        while name in self.name_map or (check_path and (self.path / name).exists()):
            name = f'{name}_{i}'
            i += 1
        return name

    def index(self, name: str) -> int:
        return self.files.index(self.name_map[name])

    def try_undelete(self, name: str) -> tuple[float, ManifestFile] | None:
        """If the given name is in the deleted files list, remove it from the list"""
        for i, (_, mf) in enumerate(self.deleted_files):
            if mf.name == name:
                deletion = self.deleted_files[i]
                del self.deleted_files[i]
                return deletion
        return None

    def _insert(self, mf: ManifestFile, index: int | None) -> tuple[float, ManifestFile] | None:
        self.name_map[mf.name] = mf
        if index is None or index >= len(self.files):
            self.files.append(mf)
        else:
            self.files.insert(index, mf)

        return self.try_undelete(mf.name)

    def add(self, path: Path, index: int = None, name: str = None, fmt: str = None) -> ManifestFile:
        new_path = self.path / path.name
        i = 0
        while new_path.exists():
            new_path = self.path / f'{new_path.stem}_{i}{new_path.suffix}'
            i += 1

        if name is None:
            name = new_path.stem
        if name in self.name_map:
            raise KeyError(f'There is already an entry named {name}')

        if path != new_path:
            shutil.copyfile(path, new_path)
        mf = ManifestFile(name, new_path, False, fmt)
        undelete = self._insert(mf, index)
        self.pending_changes.append(AddFile(mf, undelete))
        return mf

    def add_raw(self, data: bytes, index: int = None, name: str = None, fmt: str = None) -> ManifestFile:
        if index is None:
            index = len(self.files)

        if name is None:
            name = self.get_unique_name(f'{index:03}')
        elif name in self.name_map:
            raise KeyError(f'There is already an entry named {name}')

        filename = name
        if fmt:
            ext = f'.{fmt}'
            if not filename.endswith(ext):
                filename += ext

        new_path = self.path / filename
        i = 0
        while new_path.exists():
            new_path = self.path / f'{new_path.stem}_{i}{new_path.suffix}'
            i += 1

        new_path.write_bytes(data)
        mf = ManifestFile(name, new_path, False, fmt)
        undelete = self._insert(mf, index)
        self.pending_changes.append(AddFile(mf, undelete))
        return mf

    def add_manifest(self, sub_manifest: Manifest, index: int = None, name: str = None,
                     fmt: str = None, flatten: bool = False) -> ManifestFile:
        if sub_manifest is self:
            raise ValueError('Cannot add a manifest to itself')

        if not sub_manifest.path.is_relative_to(self.path):
            raise ValueError('Manifest members must be located within the manifest directory')

        if name is None:
            name = self.get_unique_name(f'{index:03}')
        elif name in self.name_map:
            raise KeyError(f'There is already an entry named {name}')

        mf = ManifestFile(name, sub_manifest.path, True, fmt, flatten)
        undelete = self._insert(mf, index)
        self.pending_changes.append(AddManifest(mf, sub_manifest, undelete))
        if flatten:
            return self.expand_file(sub_manifest[0])
        return mf

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

        deletion_index = bisect.bisect_left(self.deleted_files, mtime, key=lambda df: df[0])
        for _, mf in self.deleted_files[deletion_index:]:
            yield mf

    def is_modified_since(self, mtime: float) -> bool:
        for _ in self.get_files_modified_since(mtime):
            return True
        return False

    def rename(self, key: int | str, name: str, rename_file: bool = True, ext: str = None) -> ManifestFile:
        """
        Rename a file in the manifest by index or name

        :param key: Index or name of the file to rename.
        :param name: New name of the file
        :param rename_file: Whether to rename the actual file on the filesystem. Note that this will not take effect
                            until the manifest is saved.
        :param ext: File extension to use if renaming the file. If not provided, the file extension will be unchanged.
        """
        mf = self.files[key] if isinstance(key, int) else self.name_map[key]
        if name != mf.name:
            if name in self.name_map:
                raise KeyError(f'There is already an entry named {name}')
            old_name = mf.name
            if mf.is_manifest:
                sub_manifest = Manifest.load_from(mf.path)
                sub_manifest.name = name
                if mf.flatten:
                    sub_manifest.rename(0, name, rename_file)
            else:
                sub_manifest = None
            del self.name_map[mf.name]
            mf.name = name
            self.name_map[name] = mf
            self.pending_changes.append(Rename(mf, old_name, rename_file, ext, sub_manifest))
        return mf

    @classmethod
    def load_from(cls, path: Path) -> Manifest:
        """
        Load a manifest from a given path

        :param path: Path where the manifest is stored
        :return: The manifest object
        """
        if (manifest := cls.get_if_loaded(path)) is not None:
            return manifest
        manifest = cls(path)
        manifest.load()
        return manifest

    @classmethod
    def get_if_loaded(cls, path: Path) -> Manifest | None:
        return cls._loaded_manifests.get(path)

    @classmethod
    def revert_all_unsaved_changes(cls):
        for manifest in cls._loaded_manifests.values():
            manifest.undo()

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
