import tkinter as tk
from tkinter import ttk
from typing import Callable

from galsdk.model import ActorModel
from galsdk.room import ActorObject
from galsdk.ui.util import validate_int, validate_float, StringVar


class ActorEditor(ttk.Frame):
    def __init__(self, actor: ActorObject, actor_models: list[ActorModel | None],
                 actor_instance_health: list[tuple[int, int]], on_update_type: Callable[[ActorObject], None],
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        self.actor_models = actor_models
        self.actor_instance_health = actor_instance_health
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

        self.x_var = StringVar(self, str(self.actor.position.game_x))
        self.x_var.trace_add('write', lambda *_: self.on_change_pos('x', self.x_var))
        x_label = ttk.Label(self, text='X:', anchor=tk.W)
        x_input = ttk.Entry(self, textvariable=self.x_var, validate='all', validatecommand=validator)

        self.y_var = StringVar(self, str(self.actor.position.game_y))
        self.y_var.trace_add('write', lambda *_: self.on_change_pos('y', self.y_var))
        y_label = ttk.Label(self, text='Y:', anchor=tk.W)
        y_input = ttk.Entry(self, textvariable=self.y_var, validate='all', validatecommand=validator)

        self.z_var = StringVar(self, str(self.actor.position.game_z))
        self.z_var.trace_add('write', lambda *_: self.on_change_pos('z', self.z_var))
        z_label = ttk.Label(self, text='Z:', anchor=tk.W)
        z_input = ttk.Entry(self, textvariable=self.z_var, validate='all', validatecommand=validator)

        self.orientation_var = StringVar(self, str(self.actor.angle))
        self.orientation_var.trace_add('write', self.on_change_orientation)
        orientation_label = ttk.Label(self, text='Orientation:', anchor=tk.W)
        orientation_input = ttk.Entry(self, textvariable=self.orientation_var, validate='all',
                                      validatecommand=float_validator)

        health_str, health_state = self.get_health_info()
        self.health_var = tk.StringVar(self, health_str)
        self.health_var.trace_add('write', self.on_change_health)
        health_label = ttk.Label(self, text='Health:', anchor=tk.W)
        self.health_input = ttk.Entry(self, textvariable=self.health_var, validate='all', validatecommand=validator,
                                      state=health_state)

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
        health_label.grid(row=6, column=0)
        self.health_input.grid(row=6, column=1)

        id_input.focus_force()

        self.actor.on_transform(self.on_object_transform)

    def get_health_info(self) -> tuple[str, str]:
        if self.actor.id < len(self.actor_instance_health):
            health_str = str(self.actor_instance_health[self.actor.id][0])
            health_state = tk.NORMAL
        else:
            health_str = '0'
            health_state = tk.DISABLED
        return health_str, health_state

    def on_change_health(self, *_):
        if self.actor.id >= len(self.actor_instance_health):
            return
        unknown = self.actor_instance_health[self.actor.id][1]
        self.actor_instance_health[self.actor.id] = (int(self.health_var.get() or '0'), unknown)

    def on_change_orientation(self, *_):
        self.actor.angle = float(self.orientation_var.get() or '0')
        self.actor.update_position()

    def on_change_id(self, *_):
        self.actor.id = int(self.id_var.get() or '0')
        health_str, health_state = self.get_health_info()
        self.health_var.set(health_str)
        self.health_input.configure(state=health_state)

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

    def on_object_transform(self, _):
        self.orientation_var.set_no_trace(str(self.actor.angle))
        self.x_var.set_no_trace(str(self.actor.position.game_x))
        self.y_var.set_no_trace(str(self.actor.position.game_y))
        self.z_var.set_no_trace(str(self.actor.position.game_z))

    def destroy(self):
        self.actor.remove_on_transform(self.on_object_transform)
        super().destroy()
