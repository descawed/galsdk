import tkinter as tk
from abc import ABCMeta, abstractmethod
from tkinter import ttk

from direct.showbase.ShowBase import DirectObject, ShowBase
from direct.task import Task
from panda3d.core import GeomNode, MouseButton, NodePath, WindowProperties

from galsdk.model import Model
from galsdk.project import Project
from galsdk.ui.tab import Tab


class ModelViewer(ttk.Frame):
    ROTATE_SCALE_X = 100000
    ROTATE_SCALE_Y = 10000
    PAN_SCALE_X = 1000
    PAN_SCALE_Y = 1000
    MIN_ZOOM = 1
    MAX_ZOOM = 50
    DEFAULT_ZOOM = 25

    def __init__(self, name: str, base: ShowBase, width: int, height: int, *args, **kwargs):
        if 'width' not in kwargs:
            kwargs['width'] = width
        if 'height' not in kwargs:
            kwargs['height'] = height

        super().__init__(*args, **kwargs)
        self.name = name
        self.base = base
        self.last_x = 0
        self.last_y = 0
        self.was_dragging_last_frame = False
        self.was_panning_last_frame = False

        props = WindowProperties()
        props.setParentWindow(self.winfo_id())
        props.setOrigin(0, 0)
        props.setSize(1280, 720)
        self.window = self.base.open_window(props)

        self.render_target = NodePath(f'model_render_{name}')
        self.camera = self.base.makeCamera(self.window)
        self.camera.reparentTo(self.render_target)
        self.camera.setPos(0, self.DEFAULT_ZOOM, 2)

        self.node = GeomNode(f'model_viewer_{name}')
        self.node_path = self.render_target.attachNewNode(self.node)
        self.camera.lookAt(self.node_path)

        # tkinter input events don't fire on the model_frame, so we have to use panda's input functionality
        self.region = self.window.makeDisplayRegion(0, 1, 0, 1)
        self.base.setupMouse(self.window)
        self.base.mouseWatcherNode.setDisplayRegion(self.region)

        self.wheel_listener = DirectObject.DirectObject()
        self.wheel_listener.accept('wheel_up', self.zoom, extraArgs=[-1])
        self.wheel_listener.accept('wheel_down', self.zoom, extraArgs=[1])

        self.base.taskMgr.add(self.watch_mouse, f'model_input_{name}')

    def set_model(self, model: Model | None):
        self.node.removeAllGeoms()
        if model is not None:
            panda_model = model.get_panda3d_model()
            panda_texture = model.get_panda3d_texture()
            self.node.addGeom(panda_model)
            self.node_path.setTexture(panda_texture, 1)
            self.node_path.setHpr(0, 0, 0)
            self.camera.setPos(0, self.DEFAULT_ZOOM, 2)

    def zoom(self, direction: int):
        new_zoom = self.camera.getY() + direction
        if new_zoom < self.MIN_ZOOM:
            new_zoom = self.MIN_ZOOM
        elif new_zoom > self.MAX_ZOOM:
            new_zoom = self.MAX_ZOOM
        self.camera.setY(new_zoom)

    def watch_mouse(self, _) -> int:
        if not self.base.mouseWatcherNode.hasMouse() or not self.window.is_active():
            return Task.cont

        # rotate the model with left click, pan with middle click
        is_dragging = self.base.mouseWatcherNode.isButtonDown(MouseButton.one())
        is_panning = self.base.mouseWatcherNode.isButtonDown(MouseButton.two())
        if is_dragging or is_panning:
            mouse_x = self.base.mouseWatcherNode.getMouseX()
            mouse_y = self.base.mouseWatcherNode.getMouseY()
            x_diff = (mouse_x - self.last_x) / self.window.getXSize()
            y_diff = (mouse_y - self.last_y) / self.window.getYSize()

            # don't do anything unless we've been dragging for at least one frame
            if is_dragging and self.was_dragging_last_frame:
                # this seems to be relative to any existing rotations, whereas setPos is absolute
                self.node_path.setH(self.node_path, x_diff * self.ROTATE_SCALE_X % 360)
                self.node_path.setP(self.node_path, y_diff * self.ROTATE_SCALE_Y % 360)

            if is_panning and self.was_panning_last_frame:
                self.camera.setX(self.camera.getX() + x_diff * self.PAN_SCALE_X)
                self.camera.setZ(self.camera.getZ() - y_diff * self.PAN_SCALE_Y)

            self.last_x = mouse_x
            self.last_y = mouse_y

        self.was_dragging_last_frame = is_dragging
        self.was_panning_last_frame = is_panning

        return Task.cont

    def set_active(self, is_active: bool):
        self.window.set_active(is_active)
        if is_active:
            self.base.setupMouse(self.window)
            self.base.mouseWatcherNode.setDisplayRegion(self.region)


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
