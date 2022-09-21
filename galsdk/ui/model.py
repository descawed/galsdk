import tkinter as tk
from tkinter import ttk

from direct.showbase.ShowBase import DirectObject, ShowBase
from direct.task import Task
from panda3d.core import GeomNode, MouseButton, NodePath, WindowProperties

from galsdk.ui.tab import Tab
from galsdk.project import Project


class ModelTab(Tab):
    """Tab for viewing game models"""

    ROTATE_SCALE_X = 100000
    ROTATE_SCALE_Y = 10000
    PAN_SCALE_X = 1000
    PAN_SCALE_Y = 1000
    MIN_ZOOM = 1
    MAX_ZOOM = 50
    DEFAULT_ZOOM = 25

    def __init__(self, project: Project, base: ShowBase):
        super().__init__('Models', project)
        self.base = base
        self.models = []
        self.current_index = None
        self.last_x = 0
        self.last_y = 0
        self.was_dragging_last_frame = False
        self.was_panning_last_frame = False

        self.tree = ttk.Treeview(self, selectmode='browse', show='tree')
        scroll = ttk.Scrollbar(self, command=self.tree.yview, orient='vertical')
        self.tree.configure(yscrollcommand=scroll.set)

        self.tree.insert('', tk.END, text='Actors', iid='actors')
        for model in self.project.get_actor_models():
            model_id = len(self.models)
            self.models.append(model)
            self.tree.insert('actors', tk.END, text=model.name, iid=str(model_id))

        self.tree.insert('', tk.END, text='Items', iid='items')
        for model in self.project.get_item_models():
            model_id = len(self.models)
            self.models.append(model)
            self.tree.insert('items', tk.END, text=model.name, iid=str(model_id))

        self.model_frame = ttk.Frame(self, width=1280, height=720)

        props = WindowProperties()
        props.setParentWindow(self.model_frame.winfo_id())
        props.setOrigin(0, 0)
        props.setSize(1280, 720)
        self.window = self.base.open_window(props)

        self.render_target = NodePath('model_render')
        self.camera = self.base.makeCamera(self.window)
        self.camera.reparentTo(self.render_target)
        self.camera.setPos(0, self.DEFAULT_ZOOM, 2)

        self.node = GeomNode('model_viewer')
        self.node_path = self.render_target.attachNewNode(self.node)
        self.camera.lookAt(self.node_path)

        # tkinter input events don't fire on the model_frame, so we have to use panda's input functionality
        self.region = self.window.makeDisplayRegion(0, 1, 0, 1)
        self.base.setupMouse(self.window)
        self.base.mouseWatcherNode.setDisplayRegion(self.region)

        self.wheel_listener = DirectObject.DirectObject()
        self.wheel_listener.accept('wheel_up', self.zoom, extraArgs=[-1])
        self.wheel_listener.accept('wheel_down', self.zoom, extraArgs=[1])

        self.tree.grid(row=0, column=0, sticky=tk.NS + tk.W)
        scroll.grid(row=0, column=1, sticky=tk.NS)
        self.model_frame.grid(row=0, column=2, sticky=tk.NS + tk.E)

        self.grid_columnconfigure(2, weight=1)

        self.tree.bind('<<TreeviewSelect>>', self.select_model)
        self.base.taskMgr.add(self.watch_mouse, 'model_input')

    def zoom(self, direction: int):
        new_zoom = self.camera.getY() + direction
        if new_zoom < self.MIN_ZOOM:
            new_zoom = self.MIN_ZOOM
        elif new_zoom > self.MAX_ZOOM:
            new_zoom = self.MAX_ZOOM
        self.camera.setY(new_zoom)

    def watch_mouse(self, _) -> int:
        if not self.base.mouseWatcherNode.hasMouse():
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

    def select_model(self, _):
        try:
            index = int(self.tree.selection()[0])
        except ValueError:
            # not a model
            return

        if index != self.current_index:
            self.current_index = index
            model = self.models[index]

            panda_model = model.get_panda3d_model()
            panda_texture = model.get_panda3d_texture()
            self.node.removeAllGeoms()
            self.node.addGeom(panda_model)
            self.node_path.setTexture(panda_texture, 1)
            self.node_path.setHpr(0, 0, 0)
            self.camera.setPos(0, self.DEFAULT_ZOOM, 2)
