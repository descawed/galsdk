import tkinter as tk
from pathlib import Path
from tkinter import ttk

from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import AudioSound, AudioManager, CardMaker, NodePath, MovieTexture, WindowProperties

from galsdk.ui.tab import Tab
from galsdk.project import Project, Stage


class MovieTab(Tab):
    """Tab for viewing FMVs"""

    def __init__(self, project: Project, base: ShowBase):
        super().__init__('Movie', project)
        self.base = base
        self.movies = []
        self.current_index = None
        self.player = None

        self.tree = ttk.Treeview(self, selectmode='browse', show='tree')
        scroll = ttk.Scrollbar(self, command=self.tree.yview, orient='vertical')
        self.tree.configure(yscrollcommand=scroll.set)

        for stage in Stage:
            stage: Stage
            self.tree.insert('', tk.END, text=f'Stage {stage}', iid=stage, open=False)

            for movie in self.project.get_stage_movies(stage):
                movie_id = len(self.movies)
                self.movies.append(movie)
                self.tree.insert(stage, tk.END, text=movie.name, iid=str(movie_id))

        self.movie_frame = ttk.Frame(self, width=320, height=240)

        props = WindowProperties()
        props.setParentWindow(self.movie_frame.winfo_id())
        props.setOrigin(0, 0)
        props.setSize(320, 240)
        self.window = self.base.open_window(props)

        # make 2d render target for this window
        self.render_target = NodePath('movie_render2d')
        self.camera = self.base.makeCamera2d(self.window)
        self.camera.reparentTo(self.render_target)

        # prepare card to display video on
        self.card_maker = CardMaker('FMV')
        self.card_maker.setFrameFullscreenQuad()
        # noinspection PyArgumentList
        self.card = None

        controls_frame = ttk.Frame(self)
        self.play_pause_text = tk.StringVar(value='\u25b6')
        self.play_pause = ttk.Button(controls_frame, textvariable=self.play_pause_text, command=self.play_pause)
        self.timeline_var = tk.DoubleVar(value=0.)
        self.timeline = ttk.Scale(controls_frame, from_=0., to=1., variable=self.timeline_var,
                                  command=self.change_timeline)

        self.play_pause.pack(anchor=tk.CENTER, side=tk.LEFT)
        self.timeline.pack(expand=1, anchor=tk.CENTER, fill=tk.BOTH, side=tk.LEFT)

        self.tree.grid(row=0, column=0, rowspan=2, sticky=tk.NS+tk.W)
        scroll.grid(row=0, column=1, rowspan=2, sticky=tk.NS)
        self.movie_frame.grid(row=0, column=2, sticky=tk.NS+tk.E)
        controls_frame.grid(row=1, column=2, sticky=tk.S+tk.EW)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(2, weight=1)

        self.tree.bind('<<TreeviewSelect>>', self.select_movie)

    def update_ui(self, _):
        if self.player.status() == AudioSound.PLAYING:
            sfx_len = self.player.length()
            sfx_time = self.player.getTime()
            self.timeline_var.set(sfx_time / sfx_len)
            self.play_pause_text.set('\u23f8')
        else:
            self.play_pause_text.set('\u25b6')
        return Task.cont

    def select_movie(self, _):
        try:
            index = int(self.tree.selection()[0])
        except ValueError:
            # not a movie
            return

        if index != self.current_index:
            self.current_index = index
            movie = self.movies[index]
            movie_tex = MovieTexture(f'movie{index}')
            # TODO: change this assert to an error dialog
            assert movie_tex.read(movie.playable_path)
            if self.card is not None:
                self.card.removeNode()
            self.card_maker.setUvRange(movie_tex)
            self.card = NodePath(self.card_maker.generate())
            self.card.reparentTo(self.render_target)
            first_set = self.player is None
            self.player = self.base.loader.loadSfx(movie.playable_path)
            movie_tex.synchronizeTo(self.player)
            self.card.setTexture(movie_tex)
            movie_tex.stop()
            if first_set:
                self.base.taskMgr.add(self.update_ui, 'movie_timer')

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
