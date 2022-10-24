from abc import ABC, abstractmethod
from pathlib import Path


class Media(ABC):
    def __init__(self, path: Path, extension: str):
        self.path = path
        self.extension = extension
        if self.extension[0] != '.':
            self.extension = '.' + self.extension

    @staticmethod
    def _prepare_path(path: Path) -> str:
        if drive := path.drive:
            # panda requires a Unix-style path
            path_str = path.as_posix()[len(drive):]
            # TODO: check if this works with UNC paths
            clean_drive = drive.replace(':', '').replace('\\', '/').lower()
            return f'/{clean_drive}{path_str}'
        else:
            return str(path)

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
                return self._prepare_path(playable_path)
            playable_path.unlink()
        self.convert(playable_path)
        return self._prepare_path(playable_path)
