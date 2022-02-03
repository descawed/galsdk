from pathlib import Path

import ffmpeg


class Movie:
    """
    Wrapper around an FMV movie file

    panda3d can use ffmpeg for video and audio playback, and ffmpeg supports STR video, so in theory we should be able
    to play the game's STR videos directly. In practice, however, the audio doesn't work because panda needs to know
    the length of the audio for proper playback and ffmpeg doesn't support detecting the audio or video duration from
    an STR video. There are few ways we could address this, but I think the most expedient is just to convert videos
    to a different format as needed.
    """

    def __init__(self, path: Path):
        """
        Create a movie referencing the STR video at the given path

        :param path: Path to the STR video
        """
        self.path = path

    @property
    def name(self) -> str:
        """Movie name"""
        return self.path.stem

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

    @property
    def playable_path(self) -> str:
        """A path to a video file suitable for playing with panda3d"""
        playable_path = self.path.with_suffix('.avi')
        if playable_path.exists():
            original_stat = self.path.lstat()
            converted_stat = playable_path.lstat()
            if original_stat.st_mtime <= converted_stat.st_mtime:
                # if we've already converted the video since the last time the original was changed, use that
                return self._prepare_path(playable_path)
            playable_path.unlink()
        # apad + shortest pads the audio with silence out to the length of the video, because some videos have audio
        # streams shorter than the video stream and this causes panda to stop playing the video early
        # we use the mjpeg codec because panda seems to have trouble with mpeg video (the video restarts after a second
        # and ends up out of sync with the audio)
        in_video = ffmpeg.input(str(self.path))
        audio = in_video.audio.filter('apad')
        ffmpeg.output(in_video.video, audio, str(playable_path), shortest=None, vcodec='mjpeg').run()
        return self._prepare_path(playable_path)
