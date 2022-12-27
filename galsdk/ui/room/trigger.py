import tkinter as tk
from tkinter import ttk

from galsdk.coords import Dimension
from galsdk.module import TriggerType, TriggerFlag
from galsdk.room import TriggerObject
from galsdk.ui.room.util import validate_int


class TriggerEditor(ttk.Frame):
    def __init__(self, trigger: TriggerObject, item_names: list[str], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.trigger = trigger
        self.conditions = ['Always', 'Not attacking', 'On activate', 'On scan (hard-coded item)', 'On scan',
                           'On scan with item', 'On use item']
        self.item_names = item_names

        validator = (self.register(validate_int), '%P')
        hex_validator = (self.register(lambda s: validate_int(s, 16)), '%P')

        self.id_var = tk.StringVar(self, str(self.trigger.id))
        id_label = ttk.Label(self, text='ID:', anchor=tk.W)
        id_input = ttk.Entry(self, textvariable=self.id_var, validate='all', validatecommand=validator)

        self.x_var = tk.StringVar(self, str(self.trigger.x_pos.game_units))
        x_label = ttk.Label(self, text='X:', anchor=tk.W)
        x_input = ttk.Entry(self, textvariable=self.x_var, validate='all', validatecommand=validator)

        self.z_var = tk.StringVar(self, str(self.trigger.z_pos.game_units))
        z_label = ttk.Label(self, text='Z:', anchor=tk.W)
        z_input = ttk.Entry(self, textvariable=self.z_var, validate='all', validatecommand=validator)

        self.width_var = tk.StringVar(self, str(self.trigger.width.game_units))
        self.height_var = tk.StringVar(self, str(self.trigger.height.game_units))

        width_label = ttk.Label(self, text='W:', anchor=tk.W)
        width_input = ttk.Entry(self, textvariable=self.width_var, validate='all', validatecommand=validator)
        height_label = ttk.Label(self, text='H:', anchor=tk.W)
        height_input = ttk.Entry(self, textvariable=self.height_var, validate='all', validatecommand=validator)

        self.enabled_var = tk.StringVar(self, f'{self.trigger.trigger.enabled_callback:08X}')
        enabled_label = ttk.Label(self, text='Enabled:', anchor=tk.W)
        enabled_input = ttk.Entry(self, textvariable=self.enabled_var, validate='all', validatecommand=hex_validator)

        self.condition_var = tk.StringVar(self, self.conditions[self.trigger.trigger.type])
        condition_label = ttk.Label(self, text='Condition:', anchor=tk.W)
        condition_select = ttk.OptionMenu(self, self.condition_var, self.condition_var.get(), *self.conditions)

        assert self.trigger.trigger.item_id >= 0
        self.item_var = tk.StringVar(self, self.item_names[self.trigger.trigger.item_id])
        self.item_label = ttk.Label(self, text='Item:', anchor=tk.W)
        self.item_select = ttk.OptionMenu(self, self.item_var, self.item_var.get(), *self.item_names)

        self.actor_1_var = tk.BooleanVar(self, bool(self.trigger.trigger.flags & TriggerFlag.ACTOR_1))
        self.actor_1_checkbox = ttk.Checkbutton(self, text='Actor 1', variable=self.actor_1_var)

        self.actor_2_var = tk.BooleanVar(self, bool(self.trigger.trigger.flags & TriggerFlag.ACTOR_2))
        self.actor_2_checkbox = ttk.Checkbutton(self, text='Actor 2', variable=self.actor_2_var)

        self.actor_3_var = tk.BooleanVar(self, bool(self.trigger.trigger.flags & TriggerFlag.ACTOR_3))
        self.actor_3_checkbox = ttk.Checkbutton(self, text='Actor 3', variable=self.actor_3_var)

        self.living_actor_var = tk.BooleanVar(self, bool(self.trigger.trigger.flags & TriggerFlag.ALLOW_LIVING_ACTOR))
        self.living_actor_checkbox = ttk.Checkbutton(self, text='Allow living actor', variable=self.living_actor_var)

        self.callback_var = tk.StringVar(self, f'{self.trigger.trigger.trigger_callback:08X}')
        self.callback_label = ttk.Label(self, text='Callback:', anchor=tk.W)
        self.callback_input = ttk.Entry(self, textvariable=self.callback_var, validate='all',
                                        validatecommand=hex_validator)

        self.id_var.trace_add('write', self.on_change_id)
        self.x_var.trace_add('write', lambda *_: self.on_change_pos('x'))
        self.z_var.trace_add('write', lambda *_: self.on_change_pos('z'))
        self.width_var.trace_add('write', lambda *_: self.on_change_size('width'))
        self.height_var.trace_add('write', lambda *_: self.on_change_size('height'))
        self.enabled_var.trace_add('write', self.on_change_enabled)
        self.condition_var.trace_add('write', self.on_change_condition)
        self.item_var.trace_add('write', self.on_change_item)
        self.actor_1_var.trace_add('write', lambda *_: self.on_change_flag(TriggerFlag.ACTOR_1, self.actor_1_var))
        self.actor_2_var.trace_add('write', lambda *_: self.on_change_flag(TriggerFlag.ACTOR_2, self.actor_2_var))
        self.actor_3_var.trace_add('write', lambda *_: self.on_change_flag(TriggerFlag.ACTOR_3, self.actor_3_var))
        self.living_actor_var.trace_add('write', lambda *_: self.on_change_flag(TriggerFlag.ALLOW_LIVING_ACTOR,
                                                                                self.living_actor_var))
        self.callback_var.trace_add('write', self.on_change_callback)

        id_label.grid(row=0, column=0)
        id_input.grid(row=0, column=1)
        x_label.grid(row=1, column=0)
        x_input.grid(row=1, column=1)
        z_label.grid(row=2, column=0)
        z_input.grid(row=2, column=1)
        width_label.grid(row=3, column=0)
        width_input.grid(row=3, column=1)
        height_label.grid(row=4, column=0)
        height_input.grid(row=4, column=1)
        enabled_label.grid(row=5, column=0)
        enabled_input.grid(row=5, column=1)
        condition_label.grid(row=6, column=0)
        condition_select.grid(row=6, column=1)
        self.toggle_item()

        id_input.focus_force()

    def toggle_item(self):
        if self.trigger.trigger.type in [TriggerType.ON_SCAN_WITH_ITEM, TriggerType.ON_USE_ITEM]:
            self.item_label.grid(row=7, column=0)
            self.item_select.grid(row=7, column=1)
            self.actor_1_checkbox.grid(row=8, column=0, columnspan=2)
            self.actor_2_checkbox.grid(row=9, column=0, columnspan=2)
            self.actor_3_checkbox.grid(row=10, column=0, columnspan=2)
            self.living_actor_checkbox.grid(row=11, column=0, columnspan=2)
            self.callback_label.grid(row=12, column=0)
            self.callback_input.grid(row=12, column=1)
        else:
            self.item_label.grid_forget()
            self.item_select.grid_forget()
            self.actor_1_checkbox.grid(row=7, column=0, columnspan=2)
            self.actor_2_checkbox.grid(row=8, column=0, columnspan=2)
            self.actor_3_checkbox.grid(row=9, column=0, columnspan=2)
            self.living_actor_checkbox.grid(row=10, column=0, columnspan=2)
            self.callback_label.grid(row=11, column=0)
            self.callback_input.grid(row=11, column=1)

    def on_change_id(self, *_):
        self.trigger.id = int(self.id_var.get() or '0')

    def on_change_enabled(self, *_):
        self.trigger.trigger.enabled_callback = int(self.enabled_var.get() or '0', 16)

    def on_change_condition(self, *_):
        self.trigger.trigger.type = TriggerType(self.conditions.index(self.condition_var.get()))
        self.toggle_item()

    def on_change_item(self, *_):
        self.trigger.trigger.item_id = self.item_names.index(self.item_var.get())

    def on_change_flag(self, flag: TriggerFlag, value: tk.BooleanVar):
        if value.get():
            self.trigger.trigger.flags |= flag
        else:
            self.trigger.trigger.flags &= ~flag

    def on_change_callback(self, *_):
        self.trigger.trigger.trigger_callback = int(self.callback_var.get() or '0', 16)

    def on_change_pos(self, axis: str):
        new_value = int(getattr(self, f'{axis}_var').get() or '0')
        setattr(self.trigger, f'{axis}_pos', Dimension(new_value, axis == 'x'))
        self.trigger.update_position()

    def on_change_size(self, dimension: str):
        var = getattr(self, f'{dimension}_var')
        var_dim = Dimension(int(var.get() or '0'), dimension == 'width')
        getattr(self.trigger, f'set_{dimension}')(var_dim)
        self.trigger.update()
