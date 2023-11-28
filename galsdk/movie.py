from pathlib import Path

import ffmpeg

from galsdk.media import Media


class Movie(Media):
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
        super().__init__(path, 'mp4')

    @property
    def name(self) -> str:
        """Movie name"""
        return self.path.stem

    def convert(self, playable_path: Path):
        # apad + shortest pads the audio with silence out to the length of the video, because some videos have audio
        # streams shorter than the video stream and this causes panda to stop playing the video early
        in_video = ffmpeg.input(str(self.path))
        audio = in_video.audio.filter('apad')
        ffmpeg.output(in_video.video, audio, str(playable_path), shortest=None).run()
