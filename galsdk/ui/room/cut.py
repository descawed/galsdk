import tkinter as tk
from tkinter import ttk

from galsdk.coords import Dimension
from galsdk.room import CameraCutObject
from galsdk.ui.room.util import validate_int


class CameraCutEditor(ttk.Frame):
    def __init__(self, cut: CameraCutObject, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cut = cut

        validator = (self.register(validate_int), '%P')

        self.id_var = tk.StringVar(self, str(self.cut.camera_id))
        self.id_var.trace_add('write', self.on_change_id)
        id_label = ttk.Label(self, text='Camera:', anchor=tk.W)
        id_input = ttk.Entry(self, textvariable=self.id_var, validate='all', validatecommand=validator)
        id_label.grid(row=0, column=0)
        id_input.grid(row=0, column=1)

        self.position_variables = []
        for i in range(4):
            point = getattr(self.cut, f'p{i + 1}')
            x_var = tk.StringVar(self, str(point.game_x))
            x_var.trace_add('write', lambda *_: self.on_change_pos(i, 'x'))
            z_var = tk.StringVar(self, str(point.game_z))
            z_var.trace_add('write', lambda *_: self.on_change_pos(i, 'z'))
            x_label = ttk.Label(self, text=f'X{i + 1}:', anchor=tk.W)
            x_input = ttk.Entry(self, textvariable=x_var, validate='all', validatecommand=validator)
            z_label = ttk.Label(self, text=f'Z{i + 1}:', anchor=tk.W)
            z_input = ttk.Entry(self, textvariable=z_var, validate='all', validatecommand=validator)
            self.position_variables.append((x_var, z_var))

            x_label.grid(row=i*2 + 1, column=0)
            x_input.grid(row=i*2 + 1, column=1)
            z_label.grid(row=(i+1)*2, column=0)
            z_input.grid(row=(i+1)*2, column=1)

        id_input.focus_force()

    def on_change_id(self, *_):
        self.cut.camera_id = int(self.id_var.get() or '0')

    def on_change_pos(self, index: int, axis: str):
        is_x = axis == 'x'
        var = self.position_variables[index][int(is_x)]
        new_value = int(var.get() or '0')
        setattr(getattr(self.cut, f'p{index + 1}'), axis, Dimension(new_value, is_x))
        self.cut.recalculate_center()
        self.cut.update_position()
