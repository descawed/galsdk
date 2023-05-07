import tkinter as tk
from tkinter import ttk

from direct.showbase.ShowBase import DirectObject, ShowBase
from direct.task import Task
from panda3d.core import GraphicsWindow, MouseButton, NativeWindowHandle, NodePath, TransparencyAttrib, WindowProperties


class Viewport(ttk.Frame):
    ROTATE_SCALE_X = 100000
    ROTATE_SCALE_Y = 10000
    PAN_SCALE_X = 1000
    PAN_SCALE_Y = 1000
    DEFAULT_MIN_ZOOM = 3
    DEFAULT_MAX_ZOOM = 50
    DEFAULT_ZOOM = 20
    DEFAULT_HEIGHT = 0
    FOCAL_LENGTH = 700

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
        self.target_orbit = None
        self.min_zoom = self.DEFAULT_MIN_ZOOM
        self.max_zoom = self.DEFAULT_MAX_ZOOM
        self._window = None
        self.camera = None
        self.region = None
        self.wheel_listener = None
        self.aspect_ratio = width / height

        self.render_target = NodePath(f'viewport_render_{name}')
        self.render_target.setTransparency(TransparencyAttrib.M_alpha)

    def resize(self, width: int, height: int, keep_aspect_ratio: bool = False):
        if self._window:
            x = y = 0
            new_width = width
            new_height = height
            if keep_aspect_ratio:
                if self.aspect_ratio < 1:
                    new_width = self.aspect_ratio * height
                    if new_width > width:
                        new_width = width
                        new_height = new_width / self.aspect_ratio
                else:
                    new_height = width / self.aspect_ratio
                    if new_height > height:
                        new_height = height
                        new_width = self.aspect_ratio * new_height
                x = int((width - new_width) / 2)
                y = int((height - new_height) / 2)
                new_width = int(new_width)
                new_height = int(new_height)
            else:
                self.aspect_ratio = width / height

            old_props = self._window.getProperties()
            if new_width == old_props.getXSize() and new_height == old_props.getYSize():
                return

            props = WindowProperties()
            props.setOrigin(x, y)
            props.setSize(new_width, new_height)
            self._window.requestProperties(props)
            self.configure(width=width, height=height)
            if not keep_aspect_ratio:
                # this ensures that when the aspect ratio of the window changes, the view isn't stretched and squished
                lens = self.camera.node().getLens()
                lens.setFilmSize(width, height)
                lens.setFocalLength(self.FOCAL_LENGTH)

    @property
    def window(self) -> GraphicsWindow:
        if self._window is None:
            self.update()
            width = self.winfo_width()
            height = self.winfo_height()

            props = WindowProperties()
            props.setParentWindow(NativeWindowHandle.makeInt(self.winfo_id()))
            props.setOrigin(0, 0)
            props.setSize(width, height)
            self._window = self.base.open_window(props)

            self.camera = self.base.makeCamera(self._window)
            self.camera.reparentTo(self.render_target)
            self.camera.setPos(0, self.DEFAULT_ZOOM, 2)
            # lens = self.camera.node().getLens()
            # lens.setFilmSize(width, height)
            # lens.setFocalLength(self.FOCAL_LENGTH)

            # tkinter input events don't fire on the model_frame, so we have to use panda's input functionality
            self.region = self.window.makeDisplayRegion(0, 1, 0, 1)
            self.base.setupMouse(self._window)
            self.base.mouseWatcherNode.setDisplayRegion(self.region)

            self.wheel_listener = DirectObject.DirectObject()
            self.wheel_listener.accept('wheel_up', self.zoom, extraArgs=[1])
            self.wheel_listener.accept('wheel_down', self.zoom, extraArgs=[-1])

            self.base.taskMgr.add(self.watch_mouse, f'viewport_input_{self.name}')

        return self._window

    def zoom(self, direction: int):
        if not self.base.mouseWatcherNode.hasMouse() or not self.window.is_active():
            return

        if self.target:
            current_zoom = self.camera.getDistance(self.target)
            new_zoom = current_zoom - direction
            if new_zoom < self.min_zoom:
                new_direction = current_zoom - self.min_zoom
            elif new_zoom > self.max_zoom:
                new_direction = self.max_zoom - current_zoom
            else:
                new_direction = direction
            camera_pos = self.camera.getPos(self.render_target)
            vector = self.target.getPos(self.render_target) - camera_pos
            vector.normalize()
            self.camera.setPos(self.render_target, camera_pos + vector * new_direction)
        else:
            self.camera.setY(self.camera, direction)

    def set_target(self, target: NodePath, camera_pos: tuple[float, float, float] = None):
        self.target = target
        if camera_pos is None:
            camera_pos = (0, self.DEFAULT_ZOOM, self.DEFAULT_HEIGHT)
        # prepare camera for orbit
        if self.target_orbit is not None:
            self.target_orbit.removeNode()
        self.target_orbit = self.target.attachNewNode(f'viewport_orbit_{self.name}')
        self.camera.reparentTo(self.target_orbit)
        self.camera.setPos(*camera_pos)
        self.camera.lookAt(self.target)

    def clear_target(self):
        self.camera.wrtReparentTo(self.render_target)
        self.target = None
        if self.target_orbit is not None:
            self.target_orbit.removeNode()
        self.target_orbit = None

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
            if is_dragging and self.was_dragging_last_frame and self.target_orbit:
                self.target_orbit.setH(self.target_orbit, -x_diff * self.ROTATE_SCALE_X % 360)
                self.target_orbit.setP(self.target_orbit, -y_diff * self.ROTATE_SCALE_Y % 360)

            if is_panning and self.was_panning_last_frame:
                self.camera.setX(self.camera, self.camera.getX(self.camera) - x_diff * self.PAN_SCALE_X)
                self.camera.setZ(self.camera, self.camera.getZ(self.camera) - y_diff * self.PAN_SCALE_Y)

            self.last_x = mouse_x
            self.last_y = mouse_y

        self.was_dragging_last_frame = is_dragging
        self.was_panning_last_frame = is_panning

        return Task.cont

    def set_active(self, is_active: bool):
        # we need to defer creation of the window until we're visible because on Linux with X, the parent window
        # (i.e. the X window corresponding to this widget) isn't ready until then
        if self._window is not None or is_active:
            self.window.set_active(is_active)
            if is_active:
                self.base.setupMouse(self.window)
                self.base.mouseWatcherNode.setDisplayRegion(self.region)
