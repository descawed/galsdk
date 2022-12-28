import tkinter as tk
from abc import ABCMeta, abstractmethod
from tkinter import ttk

from direct.showbase.ShowBase import ShowBase
from panda3d.core import GeomNode

from galsdk.model import Model
from galsdk.project import Project
from galsdk.ui.tab import Tab
from galsdk.ui.viewport import Viewport


class ModelViewer(Viewport):
    def __init__(self, name: str, base: ShowBase, width: int, height: int, *args, **kwargs):
        super().__init__(name, base, width, height, *args, **kwargs)

        self.node = GeomNode(f'model_viewer_{name}')
        self.node_path = self.render_target.attachNewNode(self.node)
        self.camera.lookAt(self.node_path)

    def set_model(self, model: Model | None):
        self.node.removeAllGeoms()
        if model is not None:
            panda_model = model.get_panda3d_model()
            panda_texture = model.get_panda3d_texture()
            self.node.addGeom(panda_model)
            self.node_path.setTexture(panda_texture, 1)
            self.node_path.setHpr(0, 0, 0)
            self.set_target(self.node_path)
        else:
            self.clear_target()

    def handle_mouse(self, is_dragging: bool, is_panning: bool, x_diff: float, y_diff: float):
        # don't do anything unless we've been dragging for at least one frame
        if is_dragging and self.was_dragging_last_frame:
            # this seems to be relative to any existing rotations, whereas setPos is absolute
            self.node_path.setH(self.node_path, x_diff * self.ROTATE_SCALE_X % 360)
            self.node_path.setP(self.node_path, y_diff * self.ROTATE_SCALE_Y % 360)


class ModelViewerTab(Tab, metaclass=ABCMeta):
    """Tab for viewing arbitrary 3D models from the game"""

    def __init__(self, name: str, project: Project, base: ShowBase):
        super().__init__(name, project)
        self.base = base
        self.models = []
        self.current_index = None

        self.tree = ttk.Treeview(self, selectmode='browse', show='tree')
        scroll = ttk.Scrollbar(self, command=self.tree.yview, orient='vertical')
        self.tree.configure(yscrollcommand=scroll.set)

        self.model_frame = ModelViewer(name.lower(), self.base, 1280, 720, self)
        self.fill_tree()

        self.tree.grid(row=0, column=0, sticky=tk.NS + tk.W)
        scroll.grid(row=0, column=1, sticky=tk.NS)
        self.model_frame.grid(row=0, column=2, sticky=tk.NS + tk.E)

        self.grid_columnconfigure(2, weight=1)

        self.tree.bind('<<TreeviewSelect>>', self.select_model)

    @abstractmethod
    def fill_tree(self):
        pass

    def select_model(self, _):
        try:
            index = int(self.tree.selection()[0])
        except ValueError:
            # not a model
            return

        if index != self.current_index:
            self.current_index = index
            self.model_frame.set_model(self.models[index])

    def set_active(self, is_active: bool):
        self.model_frame.set_active(is_active)
