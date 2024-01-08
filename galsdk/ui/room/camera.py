import tkinter as tk
from tkinter import ttk
from typing import Callable

from galsdk.room import CameraObject
from galsdk.ui.util import validate_int, validate_float, StringVar


class CameraEditor(ttk.Frame):
    def __init__(self, camera: CameraObject, num_bgs: int, current_bg: int, bg_change_listener: Callable[[int], None],
                 view_change_listener: Callable[[], None], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.camera = camera
        self.num_bgs = num_bgs
        self.bg_change_listener = bg_change_listener
        self.view_change_listener = view_change_listener

        validator = (self.register(validate_int), '%P')
        float_validator = (self.register(validate_float), '%P')

        self.orientation_var = tk.StringVar(self, str(self.camera.orientation))
        self.orientation_var.trace_add('write', self.on_change_orientation)
        orientation_label = ttk.Label(self, text='Orientation:', anchor=tk.W)
        orientation_input = ttk.Entry(self, textvariable=self.orientation_var, validate='all',
                                      validatecommand=validator)

        self.fov_var = tk.StringVar(self, str(self.camera.fov))
        self.fov_var.trace_add('write', self.on_change_fov)
        fov_label = ttk.Label(self, text='FOV:', anchor=tk.W)
        fov_input = ttk.Entry(self, textvariable=self.fov_var, validate='all', validatecommand=float_validator)

        self.scale_var = tk.StringVar(self, str(self.camera.scale))
        self.scale_var.trace_add('write', self.on_change_scale)
        scale_label = ttk.Label(self, text='Scale:', anchor=tk.W)
        scale_input = ttk.Entry(self, textvariable=self.scale_var, validate='all', validatecommand=validator)

        self.x_var = StringVar(self, str(self.camera.position.game_x))
        self.x_var.trace_add('write', lambda *_: self.on_change_pos('position', 'x', self.x_var))
        x_label = ttk.Label(self, text='X:', anchor=tk.W)
        x_input = ttk.Entry(self, textvariable=self.x_var, validate='all', validatecommand=validator)

        self.y_var = StringVar(self, str(self.camera.position.game_y))
        self.y_var.trace_add('write', lambda *_: self.on_change_pos('position', 'y', self.y_var))
        y_label = ttk.Label(self, text='Y:', anchor=tk.W)
        y_input = ttk.Entry(self, textvariable=self.y_var, validate='all', validatecommand=validator)

        self.z_var = StringVar(self, str(self.camera.position.game_z))
        self.z_var.trace_add('write', lambda *_: self.on_change_pos('position', 'z', self.z_var))
        z_label = ttk.Label(self, text='Z:', anchor=tk.W)
        z_input = ttk.Entry(self, textvariable=self.z_var, validate='all', validatecommand=validator)

        self.target_x_var = StringVar(self, str(self.camera.target.game_x))
        self.target_x_var.trace_add('write', lambda *_: self.on_change_pos('target', 'x', self.target_x_var))
        target_x_label = ttk.Label(self, text='Target X:', anchor=tk.W)
        target_x_input = ttk.Entry(self, textvariable=self.target_x_var, validate='all', validatecommand=validator)

        self.target_y_var = StringVar(self, str(self.camera.target.game_y))
        self.target_y_var.trace_add('write', lambda *_: self.on_change_pos('target', 'y', self.target_y_var))
        target_y_label = ttk.Label(self, text='Target Y:', anchor=tk.W)
        target_y_input = ttk.Entry(self, textvariable=self.target_y_var, validate='all', validatecommand=validator)

        self.target_z_var = StringVar(self, str(self.camera.target.game_z))
        self.target_z_var.trace_add('write', lambda *_: self.on_change_pos('target', 'z', self.target_z_var))
        target_z_label = ttk.Label(self, text='Target Z:', anchor=tk.W)
        target_z_input = ttk.Entry(self, textvariable=self.target_z_var, validate='all', validatecommand=validator)

        self.bg_var = tk.StringVar(self, str(current_bg))
        self.bg_var.trace_add('write', self.on_change_bg)

        orientation_label.grid(row=0, column=0)
        orientation_input.grid(row=0, column=1)
        fov_label.grid(row=1, column=0)
        fov_input.grid(row=1, column=1)
        scale_label.grid(row=2, column=0)
        scale_input.grid(row=2, column=1)
        x_label.grid(row=3, column=0)
        x_input.grid(row=3, column=1)
        y_label.grid(row=4, column=0)
        y_input.grid(row=4, column=1)
        z_label.grid(row=5, column=0)
        z_input.grid(row=5, column=1)
        target_x_label.grid(row=6, column=0)
        target_x_input.grid(row=6, column=1)
        target_y_label.grid(row=7, column=0)
        target_y_input.grid(row=7, column=1)
        target_z_label.grid(row=8, column=0)
        target_z_input.grid(row=8, column=1)

        if num_bgs > 1:
            bg_label = ttk.Label(self, text='BG preview:', anchor=tk.W)
            bg_select = ttk.Combobox(self, textvariable=self.bg_var, values=[str(i) for i in range(num_bgs)])
            bg_label.grid(row=9, column=0)
            bg_select.grid(row=9, column=1)

        orientation_input.focus_force()

        self.camera.on_transform(self.on_object_transform)

    def on_change_orientation(self, *_):
        self.camera.orientation = int(self.orientation_var.get() or '0')

    def on_change_fov(self, *_):
        self.camera.fov = float(self.fov_var.get() or '0')
        self.view_change_listener()

    def on_change_scale(self, *_):
        self.camera.scale = int(self.scale_var.get() or '0')

    def on_change_pos(self, position: str, axis: str, new_value: tk.StringVar):
        setattr(getattr(self.camera, position), f'game_{axis}', int(new_value.get() or '0'))
        self.camera.update_position()
        self.view_change_listener()

    def on_change_bg(self, *_):
        bg_num = int(self.bg_var.get() or '0')
        self.bg_change_listener(bg_num)

    def on_object_transform(self, _):
        self.x_var.set_no_trace(str(self.camera.position.game_x))
        self.y_var.set_no_trace(str(self.camera.position.game_y))
        self.z_var.set_no_trace(str(self.camera.position.game_z))

        self.target_x_var.set_no_trace(str(self.camera.target.game_x))
        self.target_y_var.set_no_trace(str(self.camera.target.game_y))
        self.target_z_var.set_no_trace(str(self.camera.target.game_z))

    def destroy(self):
        self.camera.remove_on_transform(self.on_object_transform)
        super().destroy()
