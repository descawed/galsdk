import tkinter as tk
from tkinter import ttk

from direct.showbase.ShowBase import ShowBase
from panda3d.core import CardMaker, NodePath, MovieTexture, WindowProperties

from galsdk.ui.tab import Tab
from galsdk.project import Project, Stage


class MovieTab(Tab):
    """Tab for viewing FMVs"""

    def __init__(self, project: Project, base: ShowBase):
        super().__init__('Movie', project)
        self.base = base
        self.movies = []
        self.current_index = None
        self.video = None

        self.tree = ttk.Treeview(self, selectmode='browse', show='tree')
        scroll = ttk.Scrollbar(self, command=self.tree.yview, orient='vertical')
        self.tree.configure(yscrollcommand=scroll.set)

        for stage in Stage:
            stage: Stage
            self.tree.insert('', tk.END, text=f'Stage {stage}', iid=stage, open=False)

            for movie in self.project.get_stage_movies(stage):
                movie_id = len(self.movies)
                self.movies.append(movie)
                self.tree.insert(stage, tk.END, text=movie.stem, iid=str(movie_id))

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
        # FIXME: set UV range properly to fix black border issue
        # noinspection PyArgumentList
        self.card = NodePath(self.card_maker.generate())
        self.card.reparentTo(self.render_target)

        controls_frame = ttk.Frame(self)
        self.play_pause = ttk.Button(controls_frame, text='\u25b6')
        self.timeline = ttk.Scale(controls_frame, from_=0., to=1., value=0.)

        self.play_pause.pack(anchor=tk.CENTER, side=tk.LEFT)
        self.timeline.pack(expand=1, anchor=tk.CENTER, fill=tk.BOTH, side=tk.LEFT)

        self.tree.grid(row=0, column=0, rowspan=2, sticky=tk.NS+tk.W)
        scroll.grid(row=0, column=1, rowspan=2, sticky=tk.NS)
        self.movie_frame.grid(row=0, column=2, sticky=tk.NS+tk.E)
        controls_frame.grid(row=1, column=2, sticky=tk.S+tk.EW)

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
            movie_path = self.movies[index]
            if drive := movie_path.drive:
                # panda requires a Unix-style path
                path_str = movie_path.as_posix()[len(drive):]
                # TODO: check if this works with UNC paths
                clean_drive = drive.replace(':', '').replace('\\', '/').lower()
                path_str = f'/{clean_drive}{path_str}'
            else:
                path_str = str(movie_path)
            movie_tex = MovieTexture(f'movie{index}')
            # TODO: change this assert to an error dialog
            assert movie_tex.read(path_str)
            self.card.setTexture(movie_tex, 1)
