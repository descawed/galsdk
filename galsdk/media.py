from abc import ABC, abstractmethod
from pathlib import Path

from galsdk import file


class Media(ABC):
    def __init__(self, path: Path, extension: str):
        self.path = path
        self.extension = extension
        if self.extension[0] != '.':
            self.extension = '.' + self.extension

    @abstractmethod
    def convert(self, playable_path: Path):
        pass

    @property
    def playable_path(self) -> str:
        """A path to a media file suitable for playing with panda3d"""
        playable_path = self.path.with_suffix(self.extension)
        if playable_path.exists():
            original_stat = self.path.lstat()
            converted_stat = playable_path.lstat()
            if original_stat.st_mtime <= converted_stat.st_mtime:
                # if we've already converted the file since the last time the original was changed, use that
                return file.panda_path(playable_path)
            playable_path.unlink()
        self.convert(playable_path)
        return file.panda_path(playable_path)
