import tkinter as tk
from tkinter import ttk

from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import AudioSound, CardMaker, NodePath, MovieTexture, WindowProperties


class MediaPlayer(ttk.Frame):
    def __init__(self, base: ShowBase, name: str, width: int, height: int, *args, use_video: bool = True,
                 **kwargs):
        super().__init__(*args, **kwargs)

        self.base = base
        self.name = name
        self.player = None
        self.card = None

        self.controls_frame = ttk.Frame(self)
        self.play_pause_text = tk.StringVar(value='\u25b6')
        self.play_pause = ttk.Button(self.controls_frame, textvariable=self.play_pause_text, command=self.play_pause)
        self.timeline_var = tk.DoubleVar(value=0.)
        self.timeline = ttk.Scale(self.controls_frame, from_=0., to=1., variable=self.timeline_var,
                                  command=self.change_timeline)

        self.play_pause.pack(anchor=tk.CENTER, side=tk.LEFT)
        self.timeline.pack(expand=1, anchor=tk.CENTER, fill=tk.BOTH, side=tk.LEFT)

        if use_video:
            self.movie_frame = ttk.Frame(self, width=width, height=height)

            window_x = self.winfo_rootx() - base.tkRoot.winfo_rootx()
            window_y = self.winfo_rooty() - base.tkRoot.winfo_rooty()

            props = WindowProperties()
            props.setParentWindow(base.tkRoot.winfo_id())
            props.setOrigin(window_x, window_y)
            props.setSize(width, height)
            self.window = self.base.open_window(props)

            # make 2d render target for this window
            self.render_target = NodePath(f'{self.name}_render2d')
            self.camera = self.base.makeCamera2d(self.window)
            self.camera.reparentTo(self.render_target)

            # prepare card to display video on
            self.card_maker = CardMaker('FMV')
            self.card_maker.setFrameFullscreenQuad()

            self.movie_frame.grid(row=0, column=0, sticky=tk.NS + tk.E)
            self.controls_frame.grid(row=1, column=0, sticky=tk.S + tk.EW)
        else:
            self.movie_frame = None
            self.window = None
            self.render_target = None
            self.camera = None
            self.card_maker = None

            self.controls_frame.grid(row=0, column=0, sticky=tk.NSEW)

        self.grid_rowconfigure(0, weight=1)

    def update_ui(self, _):
        if self.player.status() == AudioSound.PLAYING:
            sfx_len = self.player.length()
            sfx_time = self.player.getTime()
            self.timeline_var.set(sfx_time / sfx_len)
            self.play_pause_text.set('\u23f8')
        else:
            self.play_pause_text.set('\u25b6')
        return Task.cont

    def change_timeline(self, _):
        if self.player is not None:
            sfx_len = self.player.length()
            new_time = self.timeline_var.get()*sfx_len
            is_playing = self.player.status() == AudioSound.PLAYING
            if is_playing:
                self.player.stop()
            self.player.setTime(new_time)
            if is_playing:
                self.player.play()

    def play_pause(self):
        if self.player is not None:
            if self.player.status() == AudioSound.PLAYING:
                t = self.player.getTime()
                self.player.stop()
                self.player.setTime(t)
            else:
                self.player.play()

    def set_media(self, audio: AudioSound, movie: MovieTexture = None):
        first_set = self.player is None
        if not first_set:
            self.player.stop()
        self.player = audio
        if self.card is not None:
            self.card.removeNode()
        if self.movie_frame is not None:
            if movie is not None:
                self.card_maker.setUvRange(movie)
                self.card = NodePath(self.card_maker.generate())
                self.card.reparentTo(self.render_target)
                movie.synchronizeTo(self.player)
                self.card.setTexture(movie)
                movie.stop()
                self.movie_frame.grid(row=0, column=0, sticky=tk.NS + tk.E)
                self.controls_frame.grid(row=1, column=0, sticky=tk.S + tk.EW)
            else:
                self.movie_frame.grid_forget()
                self.controls_frame.grid(row=0, column=0, sticky=tk.NSEW)
        if first_set:
            self.base.taskMgr.add(self.update_ui, f'{self.name}_timer')

    def set_active(self, is_active: bool):
        if self.window is not None:
            self.window.set_active(is_active)
