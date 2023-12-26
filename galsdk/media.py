from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import ffmpeg

from galsdk import file


@dataclass
class MediaStats:
    fps: int
    frame_time: float
    num_frames: int
    duration: float


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
    def stats(self) -> MediaStats | None:
        stats = ffmpeg.probe(self.playable_path)
        # if there's a video stream, choose that; otherwise, take the audio stream
        chosen_stream = None
        for stream in stats['streams']:
            if stream['codec_type'] == 'video':
                chosen_stream = stream
                break
            if stream['codec_type'] == 'audio':
                chosen_stream = stream

        if chosen_stream is None:
            return None

        if (duration_ts := chosen_stream.get('duration_ts')) and (time_base := chosen_stream.get('time_base')):
            num, denom = time_base.split('/')
            duration = duration_ts * int(num) / int(denom)
        elif 'duration' in chosen_stream:
            duration = float(chosen_stream['duration'])
        else:
            return None  # duration is required

        fps = None
        num_frames = None
        if frame_rate := chosen_stream.get('r_frame_rate', chosen_stream.get('avg_frame_rate')):
            frames, seconds = frame_rate.split('/')
            frames = int(frames)
            seconds = int(seconds)
            # don't know what to do if it's not 1
            if seconds == 1:
                fps = frames
                if nb_frames := chosen_stream.get('nb_frames'):
                    num_frames = int(nb_frames)

        if fps is None:
            # just default to 30 since that's what the game runs at
            fps = 30

        if num_frames is None:
            num_frames = int(duration * fps)

        return MediaStats(fps, 1 / fps, num_frames, duration)

    @property
    def playable_path(self) -> Path:
        playable_path = self.path.with_suffix(self.extension)
        if playable_path.exists():
            original_stat = self.path.lstat()
            converted_stat = playable_path.lstat()
            if original_stat.st_mtime <= converted_stat.st_mtime:
                # if we've already converted the file since the last time the original was changed, use that
                return playable_path
            playable_path.unlink()
        self.convert(playable_path)
        return playable_path

    @property
    def playable_panda_path(self) -> str:
        """A path to a media file suitable for playing with panda3d"""
        return file.panda_path(self.playable_path)
