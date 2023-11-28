import tkinter as tk
from tkinter import ttk

from direct.showbase.ShowBase import ShowBase
from panda3d.core import MovieTexture

from galsdk.ui.media import MediaPlayer
from galsdk.ui.tab import Tab
from galsdk.project import Project
from galsdk.game import Stage


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

        self.player = MediaPlayer(self.base, 'movie', 320, 176, self)

        self.tree.grid(row=0, column=0, sticky=tk.NS+tk.W)
        scroll.grid(row=0, column=1, sticky=tk.NS)
        self.player.grid(row=0, column=2, sticky=tk.NSEW)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(2, weight=1)

        self.tree.bind('<<TreeviewSelect>>', self.select_movie)

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
            audio = self.base.loader.loadSfx(movie.playable_path)
            self.player.set_media(audio, movie_tex)

    def set_active(self, is_active: bool):
        self.player.set_active(is_active)

    def close(self):
        self.player.close()
