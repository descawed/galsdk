import tkinter as tk
from tkinter import ttk

from galsdk.room import EntranceObject
from galsdk.ui.room.util import validate_int, validate_float, StringVar


class EntranceEditor(ttk.Frame):
    def __init__(self, entrance: EntranceObject, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.entrance = entrance

        validator = (self.register(validate_int), '%P')
        float_validator = (self.register(validate_float), '%P')

        self.id_var = tk.StringVar(self, str(self.entrance.room_index))
        self.id_var.trace_add('write', self.on_change_id)
        id_label = ttk.Label(self, text='Room:', anchor=tk.W)
        id_input = ttk.Entry(self, textvariable=self.id_var, validate='all', validatecommand=validator)

        self.x_var = StringVar(self, str(self.entrance.position.game_x))
        self.x_var.trace_add('write', lambda *_: self.on_change_pos('x', self.x_var))
        x_label = ttk.Label(self, text='X:', anchor=tk.W)
        x_input = ttk.Entry(self, textvariable=self.x_var, validate='all', validatecommand=validator)

        self.y_var = StringVar(self, str(self.entrance.position.game_y))
        self.y_var.trace_add('write', lambda *_: self.on_change_pos('y', self.y_var))
        y_label = ttk.Label(self, text='Y:', anchor=tk.W)
        y_input = ttk.Entry(self, textvariable=self.y_var, validate='all', validatecommand=validator)

        self.z_var = StringVar(self, str(self.entrance.position.game_z))
        self.z_var.trace_add('write', lambda *_: self.on_change_pos('z', self.z_var))
        z_label = ttk.Label(self, text='Z:', anchor=tk.W)
        z_input = ttk.Entry(self, textvariable=self.z_var, validate='all', validatecommand=validator)

        self.orientation_var = StringVar(self, str(self.entrance.angle))
        self.orientation_var.trace_add('write', self.on_change_orientation)
        orientation_label = ttk.Label(self, text='Orientation:', anchor=tk.W)
        orientation_input = ttk.Entry(self, textvariable=self.orientation_var, validate='all',
                                      validatecommand=float_validator)

        id_label.grid(row=0, column=0)
        id_input.grid(row=0, column=1)
        x_label.grid(row=1, column=0)
        x_input.grid(row=1, column=1)
        y_label.grid(row=2, column=0)
        y_input.grid(row=2, column=1)
        z_label.grid(row=3, column=0)
        z_input.grid(row=3, column=1)
        orientation_label.grid(row=4, column=0)
        orientation_input.grid(row=4, column=1)

        id_input.focus_force()

        self.entrance.on_transform(self.on_object_transform)

    def on_change_orientation(self, *_):
        self.entrance.angle = float(self.orientation_var.get() or '0')
        self.entrance.update_position()

    def on_change_id(self, *_):
        self.entrance.room_index = int(self.id_var.get() or '0')

    def on_change_pos(self, axis: str, new_value: tk.StringVar):
        setattr(self.entrance.position, f'game_{axis}', int(new_value.get() or '0'))
        self.entrance.update_position()

    def on_object_transform(self, _):
        self.x_var.set_no_trace(str(self.entrance.position.game_x))
        self.y_var.set_no_trace(str(self.entrance.position.game_y))
        self.z_var.set_no_trace(str(self.entrance.position.game_z))
        self.orientation_var.set_no_trace(str(self.entrance.angle))

    def destroy(self):
        self.entrance.remove_on_transform(self.on_object_transform)
        super().destroy()
