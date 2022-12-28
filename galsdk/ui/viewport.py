from tkinter import ttk

from direct.showbase.ShowBase import DirectObject, ShowBase
from direct.task import Task
from panda3d.core import MouseButton, NodePath, TransparencyAttrib, WindowProperties, Vec3


class Viewport(ttk.Frame):
    ROTATE_SCALE_X = 100000
    ROTATE_SCALE_Y = 10000
    PAN_SCALE_X = 1000
    PAN_SCALE_Y = 1000
    DEFAULT_MIN_ZOOM = 1
    DEFAULT_MAX_ZOOM = 50
    DEFAULT_ZOOM = 25
    DEFAULT_HEIGHT = 2

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
        self.target = None
        self.min_zoom = self.DEFAULT_MIN_ZOOM
        self.max_zoom = self.DEFAULT_MAX_ZOOM

        props = WindowProperties()
        props.setParentWindow(self.winfo_id())
        props.setOrigin(0, 0)
        props.setSize(width, height)
        self.window = self.base.open_window(props)

        self.render_target = NodePath(f'viewport_render_{name}')
        self.render_target.setTransparency(TransparencyAttrib.M_alpha)
        self.camera = self.base.makeCamera(self.window)
        self.camera.reparentTo(self.render_target)
        self.camera.setPos(0, self.DEFAULT_ZOOM, 2)

        # tkinter input events don't fire on the model_frame, so we have to use panda's input functionality
        self.region = self.window.makeDisplayRegion(0, 1, 0, 1)
        self.base.setupMouse(self.window)
        self.base.mouseWatcherNode.setDisplayRegion(self.region)

        self.wheel_listener = DirectObject.DirectObject()
        self.wheel_listener.accept('wheel_up', self.zoom, extraArgs=[-1])
        self.wheel_listener.accept('wheel_down', self.zoom, extraArgs=[1])

        self.base.taskMgr.add(self.watch_mouse, f'viewport_input_{name}')

    def zoom(self, direction: int):
        if self.target:
            current_zoom = self.camera.getDistance(self.target)
        else:
            current_zoom = self.camera.getY()

        new_zoom = current_zoom + direction
        if new_zoom < self.min_zoom:
            new_zoom = self.min_zoom
        elif new_zoom > self.max_zoom:
            new_zoom = self.max_zoom

        if self.target:
            camera_pos = self.camera.getPos()
            vector = self.target.getPos() - camera_pos
            vector.normalize()
            new_direction = new_zoom - current_zoom
            self.camera.setPos(camera_pos - vector * new_direction)
        else:
            self.camera.setY(new_zoom)

    def set_target(self, target: NodePath, camera_pos: tuple[float, float, float] = None):
        self.target = target
        if camera_pos is None:
            camera_pos = (0, self.DEFAULT_ZOOM, self.DEFAULT_HEIGHT)
        self.camera.setPos(self.target, *camera_pos)
        self.camera.lookAt(self.target)

    def clear_target(self):
        self.target = None

    def handle_mouse(self, is_dragging: bool, is_panning: bool, x_diff: float, y_diff: float):
        pass

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

            self.handle_mouse(is_dragging, is_panning, x_diff, y_diff)

            if is_panning and self.was_panning_last_frame:
                self.camera.setX(self.camera, self.camera.getX(self.camera) - x_diff * self.PAN_SCALE_X)
                self.camera.setZ(self.camera, self.camera.getZ(self.camera) - y_diff * self.PAN_SCALE_Y)

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
