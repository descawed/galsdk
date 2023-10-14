import tkinter as tk
from tkinter import ttk
from typing import Callable

from galsdk.model import ActorModel
from galsdk.room import ActorObject
from galsdk.ui.room.util import validate_int, validate_float


class ActorEditor(ttk.Frame):
    def __init__(self, actor: ActorObject, actor_models: list[ActorModel],
                 on_update_type: Callable[[ActorObject], None], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        self.actor_models = actor_models
        self.actor_names = ['None']
        self.actor_names.extend(model.name for model in self.actor_models)
        self.on_update_type = on_update_type

        validator = (self.register(validate_int), '%P')
        float_validator = (self.register(validate_float), '%P')

        self.id_var = tk.StringVar(self, str(self.actor.id))
        self.id_var.trace_add('write', self.on_change_id)
        id_label = ttk.Label(self, text='ID:', anchor=tk.W)
        id_input = ttk.Entry(self, textvariable=self.id_var, validate='all', validatecommand=validator)

        self.type_var = tk.StringVar(self, self.actor_names[self.actor.type + 1])
        self.type_var.trace_add('write', self.on_change_type)
        type_label = ttk.Label(self, text='Type:', anchor=tk.W)
        type_select = ttk.OptionMenu(self, self.type_var, self.type_var.get(), *self.actor_names)

        self.x_var = tk.StringVar(self, str(self.actor.position.game_x))
        self.x_var.trace_add('write', lambda *_: self.on_change_pos('x', self.x_var))
        x_label = ttk.Label(self, text='X:', anchor=tk.W)
        x_input = ttk.Entry(self, textvariable=self.x_var, validate='all', validatecommand=validator)

        self.y_var = tk.StringVar(self, str(self.actor.position.game_y))
        self.y_var.trace_add('write', lambda *_: self.on_change_pos('y', self.y_var))
        y_label = ttk.Label(self, text='Y:', anchor=tk.W)
        y_input = ttk.Entry(self, textvariable=self.y_var, validate='all', validatecommand=validator)

        self.z_var = tk.StringVar(self, str(self.actor.position.game_z))
        self.z_var.trace_add('write', lambda *_: self.on_change_pos('z', self.z_var))
        z_label = ttk.Label(self, text='Z:', anchor=tk.W)
        z_input = ttk.Entry(self, textvariable=self.z_var, validate='all', validatecommand=validator)

        self.orientation_var = tk.StringVar(self, str(self.actor.angle))
        self.orientation_var.trace_add('write', self.on_change_orientation)
        orientation_label = ttk.Label(self, text='Orientation:', anchor=tk.W)
        orientation_input = ttk.Entry(self, textvariable=self.orientation_var, validate='all',
                                      validatecommand=float_validator)

        id_label.grid(row=0, column=0)
        id_input.grid(row=0, column=1)
        type_label.grid(row=1, column=0)
        type_select.grid(row=1, column=1)
        x_label.grid(row=2, column=0)
        x_input.grid(row=2, column=1)
        y_label.grid(row=3, column=0)
        y_input.grid(row=3, column=1)
        z_label.grid(row=4, column=0)
        z_input.grid(row=4, column=1)
        orientation_label.grid(row=5, column=0)
        orientation_input.grid(row=5, column=1)

        id_input.focus_force()

    def on_change_orientation(self, *_):
        self.actor.angle = float(self.orientation_var.get() or '0')
        self.actor.update_position()

    def on_change_id(self, *_):
        self.actor.id = int(self.id_var.get() or '0')

    def on_change_pos(self, axis: str, new_value: tk.StringVar):
        setattr(self.actor.position, f'game_{axis}', int(new_value.get() or '0'))
        self.actor.update_position()

    def on_change_type(self, *_):
        name = self.type_var.get()
        type_id = self.actor_names.index(name) - 1
        if type_id != self.actor.type:
            self.actor.type = type_id
            self.actor.model = None if type_id < 0 else self.actor_models[type_id]
            self.actor.update_model()
            self.actor.update_texture()
            self.on_update_type(self.actor)
