import sys
from enum import Enum
from pathlib import Path
from tkinter import ttk
from typing import Self

from direct.showbase.ShowBase import DirectObject, ShowBase
from direct.task import Task
from panda3d.core import (Filename, GraphicsWindow, MouseButton, NativeWindowHandle, NodePath, TransparencyAttrib,
                          WindowProperties)


CURSOR_EXT = 'xmc' if sys.platform == 'linux' else 'ico'


class Cursor(str, Enum):
    CENTER = 'center'
    VERTICAL = 'vertical'
    HORIZONTAL = 'horizontal'
    DIAGONAL_FORWARD = 'diagonal_forward'
    DIAGONAL_BACKWARD = 'diagonal_backward'

    def __str__(self) -> str:
        return self.value

    @property
    def filename(self):
        return Filename.fromOsSpecific(str(Path.cwd() / 'assets' / f'arrows_{self.value}.{CURSOR_EXT}'),
                                       Filename.TGeneral)

    @classmethod
    def from_angle(cls, angle: float) -> Self:
        # slice the circle into 30 and 60 degree arcs corresponding to each cursor we might want to show
        if 75 <= angle <= 105 or 255 <= angle <= 285:
            return cls.VERTICAL
        if angle >= 345 or angle <= 15 or 165 <= angle <= 195:
            return cls.HORIZONTAL
        if 15 < angle < 75 or 195 < angle < 255:
            return cls.DIAGONAL_FORWARD
        return cls.DIAGONAL_BACKWARD


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
        self.was_mouse1_down_last_frame = False
        self.was_mouse2_down_last_frame = False
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
        self.mouse_task = None
        self.aspect_ratio = width / height
        self.current_cursor = None

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
            if self.current_cursor is not None:
                props.setCursorFilename(self.current_cursor.filename)
            self._window.requestProperties(props)
            self.configure(width=width, height=height)
            if not keep_aspect_ratio:
                # this ensures that when the aspect ratio of the window changes, the view isn't stretched and squished
                lens = self.camera.node().getLens()
                lens.setFilmSize(width, height)
                lens.setFocalLength(self.FOCAL_LENGTH)

    def setup_window(self):
        # tkinter input events don't fire on the model_frame, so we have to use panda's input functionality
        self.region = self._window.makeDisplayRegion(0, 1, 0, 1)
        self.base.setupMouse(self._window)
        self.base.mouseWatcherNode.setDisplayRegion(self.region)

        self.wheel_listener = DirectObject.DirectObject()
        self.wheel_listener.accept('wheel_up', self.zoom, extraArgs=[1])
        self.wheel_listener.accept('wheel_down', self.zoom, extraArgs=[-1])

        self.mouse_task = self.base.taskMgr.add(self.watch_mouse, f'viewport_input_{self.name}')

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
            if self.current_cursor is not None:
                props.setCursorFilename(self.current_cursor.filename)
            self._window = self.base.open_window(props)

            self.camera = self.base.makeCamera(self._window)
            self.camera.reparentTo(self.render_target)
            self.camera.setPos(0, self.DEFAULT_ZOOM, 2)

            self.setup_window()

        return self._window

    @property
    def has_focus(self) -> bool:
        return self.base.mouseWatcherNode.hasMouse() and self.window.isActive()

    def zoom(self, direction: int):
        if not self.has_focus:
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
        if not self.has_focus:
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

        self.was_mouse1_down_last_frame = is_dragging
        self.was_dragging_last_frame = is_dragging
        self.was_mouse2_down_last_frame = is_panning
        self.was_panning_last_frame = is_panning

        return Task.cont

    def set_active(self, is_active: bool):
        # we need to defer creation of the window until we're visible because on Linux with X, the parent window
        # (i.e. the X window corresponding to this widget) isn't ready until then
        if self._window is not None or is_active:
            self.window.setActive(is_active)
            if is_active:
                self.base.setupMouse(self.window)
                self.base.mouseWatcherNode.setDisplayRegion(self.region)

    def set_cursor(self, cursor: Cursor | None):
        if self.current_cursor is not cursor:
            self.current_cursor = cursor
            old_props = self._window.getProperties()
            origin = old_props.getOrigin()
            props = WindowProperties()
            props.setOrigin(origin.getX(), origin.getY())
            props.setSize(old_props.getXSize(), old_props.getYSize())
            props.setCursorFilename(cursor.filename if cursor is not None else Filename(''))
            self._window.requestProperties(props)

    def close(self):
        if self.mouse_task is not None:
            self.base.taskMgr.remove(self.mouse_task)
            self.mouse_task = None
        if self._window is not None:
            self.base.graphicsEngine.removeWindow(self._window)
            self._window = None
