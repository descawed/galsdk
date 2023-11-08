import tkinter as tk
from tkinter import ttk
from typing import Callable

from galsdk.coords import Dimension
from galsdk.game import KEY_ITEM_NAMES, KNOWN_FUNCTIONS, MAP_NAMES, MED_ITEM_NAMES, ArgumentType, Stage
from galsdk.module import CallbackFunction, FunctionCall, TriggerType, TriggerFlag
from galsdk.room import TriggerObject
from galsdk.ui.room.util import validate_int, StringVar


class TriggerEditor(ttk.Frame):
    MAX_MESSAGE_LEN = 20

    def __init__(self, trigger: TriggerObject, messages: dict[int, str], maps: list[list[str]], movies: list[str],
                 functions: dict[int, CallbackFunction], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.trigger = trigger
        self.conditions = ['Always', 'Not attacking', 'On activate', 'On scan (hard-coded item)', 'On scan',
                           'On scan with item', 'On use item']
        self.messages = {}
        self.message_to_id = {}
        for msg_id, msg in messages.items():
            new_msg = f'{msg_id}: {msg}'
            if len(new_msg) > self.MAX_MESSAGE_LEN:
                new_msg = new_msg[:self.MAX_MESSAGE_LEN - 3] + '...'
            self.messages[msg_id] = new_msg
            self.message_to_id[new_msg] = msg_id
        self.maps = maps
        self.movies = movies
        self.functions = functions
        self.call_enabled_vars = {}
        self.return_vars = {}
        self.arg_vars = {}
        self.arg_tracers = set()
        self.map_room_links = []

        self.validator = (self.register(validate_int), '%P')
        self.hex_validator = (self.register(lambda s: validate_int(s, 16)), '%P')

        self.id_var = tk.StringVar(self, str(self.trigger.id))
        id_label = ttk.Label(self, text='ID:', anchor=tk.W)
        id_input = ttk.Entry(self, textvariable=self.id_var, validate='all', validatecommand=self.validator)

        self.x_var = StringVar(self, str(self.trigger.x_pos.game_units))
        x_label = ttk.Label(self, text='X:', anchor=tk.W)
        x_input = ttk.Entry(self, textvariable=self.x_var, validate='all', validatecommand=self.validator)

        self.z_var = StringVar(self, str(self.trigger.z_pos.game_units))
        z_label = ttk.Label(self, text='Z:', anchor=tk.W)
        z_input = ttk.Entry(self, textvariable=self.z_var, validate='all', validatecommand=self.validator)

        self.width_var = StringVar(self, str(self.trigger.width.game_units))
        self.height_var = StringVar(self, str(self.trigger.height.game_units))

        width_label = ttk.Label(self, text='W:', anchor=tk.W)
        width_input = ttk.Entry(self, textvariable=self.width_var, validate='all', validatecommand=self.validator)
        height_label = ttk.Label(self, text='H:', anchor=tk.W)
        height_input = ttk.Entry(self, textvariable=self.height_var, validate='all', validatecommand=self.validator)

        if self.trigger.trigger:
            state = tk.NORMAL
            self.last_enabled_callback = self.trigger.trigger.enabled_callback
        else:
            state = tk.DISABLED
            self.last_enabled_callback = 0
        self.enabled_var = tk.StringVar(self, f'{self.last_enabled_callback:08X}')
        enabled_label = ttk.Label(self, text='Enabled:', anchor=tk.W)
        enabled_input = ttk.Entry(self, textvariable=self.enabled_var, validate='all',
                                  validatecommand=self.hex_validator, state=state)
        self.enabled_actions_frame = None

        if self.trigger.trigger:
            value = self.conditions[self.trigger.trigger.type]
        else:
            value = 'Always'
        self.condition_var = tk.StringVar(self, value)
        self.condition_label = ttk.Label(self, text='Condition:', anchor=tk.W)
        self.condition_select = ttk.OptionMenu(self, self.condition_var, self.condition_var.get(), *self.conditions)
        self.condition_select.configure(state=state)

        item_id = self.trigger.trigger.item_id if self.trigger.trigger else 0
        self.item_var, self.item_label, self.item_select = self.make_option_select(item_id, 'Item', KEY_ITEM_NAMES)
        self.item_select.configure(state=state)

        if self.trigger.trigger:
            flags = self.trigger.trigger.flags
        else:
            flags = TriggerFlag(0)
        self.actor_1_var = tk.BooleanVar(self, bool(flags & TriggerFlag.ACTOR_1))
        self.actor_1_checkbox = ttk.Checkbutton(self, text='Actor 1', variable=self.actor_1_var, state=state)

        self.actor_2_var = tk.BooleanVar(self, bool(flags & TriggerFlag.ACTOR_2))
        self.actor_2_checkbox = ttk.Checkbutton(self, text='Actor 2', variable=self.actor_2_var, state=state)

        self.actor_3_var = tk.BooleanVar(self, bool(flags & TriggerFlag.ACTOR_3))
        self.actor_3_checkbox = ttk.Checkbutton(self, text='Actor 3', variable=self.actor_3_var, state=state)

        self.living_actor_var = tk.BooleanVar(self, bool(flags & TriggerFlag.ALLOW_LIVING_ACTOR))
        self.living_actor_checkbox = ttk.Checkbutton(self, text='Allow living actor', variable=self.living_actor_var,
                                                     state=state)

        if self.trigger.trigger:
            self.last_trigger_callback = self.trigger.trigger.trigger_callback
        else:
            self.last_trigger_callback = 0
        self.callback_var = tk.StringVar(self, f'{self.last_trigger_callback:08X}')
        self.callback_label = ttk.Label(self, text='Callback:', anchor=tk.W)
        self.callback_input = ttk.Entry(self, textvariable=self.callback_var, validate='all',
                                        validatecommand=self.hex_validator, state=state)
        self.callback_actions_frame = None

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
        self.toggle_item()

        id_input.focus_force()

        self.trigger.on_transform(self.on_object_transform)

    def make_action_frame(self, cb_address: int, show_return_value: bool = False) -> ttk.Labelframe:
        cb = self.functions[cb_address]
        stages = list(Stage)
        frame = ttk.Labelframe(self, text='Actions')
        row = 0
        if show_return_value and cb.return_value_instruction is not None and cb.return_value is not None:
            old_var = self.return_vars.get(cb_address)
            return_var, return_label, return_entry = self.make_int_entry(cb.return_value, frame, old_var,
                                                                         'Return value')
            if old_var is None:
                self.return_vars[cb_address] = return_var
                return_var.trace_add('write', self.return_value_updater(cb, self.int_value_getter(return_var)))
            return_label.grid(row=row, column=0)
            return_entry.grid(row=row, column=1)
            row += 1

        for i, call in enumerate(cb.calls):
            function = KNOWN_FUNCTIONS[call.name]
            if call.call_address not in self.call_enabled_vars:
                enabled_var = tk.BooleanVar(frame, call.is_enabled is not False)
                if call.is_enabled is not None:
                    enabled_var.trace_add('write', self.function_enabler(call, enabled_var))
                self.call_enabled_vars[call.call_address] = enabled_var
            else:
                enabled_var = self.call_enabled_vars[call.call_address]

            state = tk.DISABLED if call.is_enabled is None else tk.NORMAL
            function_check = ttk.Checkbutton(frame, text=call.name, variable=enabled_var, state=state)
            function_check.grid(row=row, column=0, columnspan=2)
            row += 1

            last_map_var = None
            for j, (arg_type, (arg_address, arg_value)) in enumerate(zip(function.arguments, call.arguments)):
                var = self.arg_vars.get(arg_address)

                match arg_type:
                    case ArgumentType.INTEGER:
                        var, label, select = self.make_int_entry(arg_value, frame, var)
                        getter = self.int_value_getter(var)
                    case ArgumentType.MAP:
                        var, label, select = self.make_option_select(arg_value, 'Map', MAP_NAMES, frame, var)
                        getter = self.string_value_getter(var, MAP_NAMES)
                        last_map_var = var
                    case ArgumentType.ROOM:
                        var, label, select = self.make_room_select(arg_value, last_map_var, frame, var)
                        getter = self.room_value_getter(var, last_map_var)
                    case ArgumentType.MESSAGE:
                        var, label, select = self.make_msg_select(arg_value, frame)
                        getter = self.msg_value_getter(var)
                    case ArgumentType.KEY_ITEM:
                        var, label, select = self.make_option_select(arg_value, 'Key Item', KEY_ITEM_NAMES, frame, var)
                        getter = self.string_value_getter(var, KEY_ITEM_NAMES)
                    case ArgumentType.MED_ITEM:
                        var, label, select = self.make_option_select(arg_value, 'Medicine', MED_ITEM_NAMES, frame, var)
                        getter = self.string_value_getter(var, MED_ITEM_NAMES)
                    case ArgumentType.STAGE:
                        var, label, select = self.make_option_select(arg_value, 'Stage', stages, frame, var)
                        getter = self.string_value_getter(var, stages)
                    case ArgumentType.MOVIE:
                        var, label, select = self.make_option_select(arg_value, 'Movie', self.movies, frame, var)
                        getter = self.string_value_getter(var, self.movies)
                    case _:
                        continue  # don't care about these arguments

                key = (i, j)
                # we need this separately from self.arguments because each usage of an argument is a separate entry in
                # a function's argument array, and we want to make sure we update all of them so we don't have
                # conflicting information when we save our changes.
                if key not in self.arg_tracers:
                    var.trace_add('write', self.argument_updater(call, j, getter))
                    self.arg_tracers.add(key)
                self.arg_vars[arg_address] = var
                label.grid(row=row, column=0)
                select.grid(row=row, column=1)
                row += 1

        return frame

    @staticmethod
    def return_value_updater(cb: CallbackFunction, getter: Callable[[], int | None]) -> Callable[..., None]:
        def updater(*_):
            value = getter()
            if value is not None:
                cb.return_value = value
        return updater

    @staticmethod
    def function_enabler(call: FunctionCall, var: tk.BooleanVar) -> Callable[..., None]:
        def enabler(*_):
            if call.is_enabled is not None:
                call.is_enabled = var.get()
        return enabler

    @staticmethod
    def argument_updater(call: FunctionCall, index: int, getter: Callable[[], int | None]) -> Callable[..., None]:
        def updater(*_):
            value = getter()
            if value is not None:
                addr = call.arguments[index][0]
                call.arguments[index] = (addr, value)
        return updater

    def msg_value_getter(self, var: tk.StringVar) -> Callable[[], int]:
        def getter() -> int:
            return self.message_to_id[var.get()]
        return getter

    def room_value_getter(self, room_var: tk.StringVar, map_var: tk.StringVar) -> Callable[[], int]:
        def getter() -> int:
            map_index = MAP_NAMES.index(map_var.get())
            return self.maps[map_index].index(room_var.get())
        return getter

    @staticmethod
    def string_value_getter(var: tk.StringVar, values: list[str]) -> Callable[[], int]:
        def getter() -> int:
            return values.index(var.get())
        return getter

    @staticmethod
    def int_value_getter(var: tk.StringVar) -> Callable[[], int | None]:
        def getter() -> int | None:
            try:
                return int(var.get())
            except ValueError:
                return None

        return getter
    
    def make_option_select(self, default_item: int, label: str, names: list[str], parent: tk.Widget = None,
                           item_var: tk.StringVar = None) -> tuple[tk.StringVar, ttk.Label, ttk.Combobox]:
        assert default_item >= 0
        if parent is None:
            parent = self
        if item_var is None:
            value = names[default_item]
            item_var = tk.StringVar(self, value)
        item_label = ttk.Label(parent, text=f'{label}:', anchor=tk.W)
        item_select = ttk.Combobox(parent, textvariable=item_var, values=names, state='readonly')
        return item_var, item_label, item_select
    
    def make_int_entry(self, default_value: int, parent: tk.Widget, int_var: tk.StringVar = None, text: str = 'Integer')\
            -> tuple[tk.StringVar, ttk.Label, ttk.Entry]:
        if int_var is None:
            int_var = tk.StringVar(self, str(default_value))
        label = ttk.Label(parent, text=f'{text}:', anchor=tk.W)
        entry = ttk.Entry(parent, textvariable=int_var, validate='all', validatecommand=self.validator)
        return int_var, label, entry

    def make_msg_select(self, default_msg: int, parent: tk.Widget, msg_var: tk.StringVar = None)\
            -> tuple[tk.StringVar, ttk.Label, ttk.Combobox]:
        assert default_msg >= 0
        if msg_var is None:
            value = self.messages[default_msg]
            msg_var = tk.StringVar(self, value)
        msg_label = ttk.Label(parent, text='Message:', anchor=tk.W)
        msg_select = ttk.Combobox(parent, textvariable=msg_var, values=list(self.messages.values()), state='readonly')
        return msg_var, msg_label, msg_select

    def make_room_select(self, default_room: int, map_var: tk.StringVar, parent: tk.Widget,
                         room_var: tk.StringVar = None) -> tuple[tk.StringVar, ttk.Label, ttk.Combobox]:
        assert default_room >= 0
        map_index = MAP_NAMES.index(map_var.get())
        current_map = self.maps[map_index]
        if room_var is None:
            value = current_map[default_room]
            room_var = tk.StringVar(self, value)
        room_label = ttk.Label(parent, text='Room:', anchor=tk.W)
        room_select = ttk.Combobox(parent, textvariable=room_var, values=current_map, state='readonly')
        link = (map_var, room_var)
        if link not in self.map_room_links:
            map_var.trace_add('write', lambda *_: self.update_room_select(map_var, room_var, room_select))
            self.map_room_links.append(link)
        return room_var, room_label, room_select

    def update_room_select(self, map_var: tk.StringVar, room_var: tk.StringVar, room_select: ttk.Combobox):
        current_map = self.maps[MAP_NAMES.index(map_var.get())]
        room_select['values'] = current_map
        room_var.set(current_map[0])

    def toggle_item(self):
        row = 6

        if self.trigger.trigger and self.trigger.trigger.enabled_callback in self.functions:
            self.enabled_actions_frame = self.configure_actions_frame(self.last_enabled_callback,
                                                                      self.trigger.trigger.enabled_callback,
                                                                      self.enabled_actions_frame, True)
            self.last_enabled_callback = self.trigger.trigger.enabled_callback
            self.enabled_actions_frame.grid(row=row, column=0, columnspan=2)
            row += 1
        elif self.enabled_actions_frame is not None:
            self.enabled_actions_frame.grid_forget()

        self.condition_label.grid(row=row, column=0)
        self.condition_select.grid(row=row, column=1)
        row += 1

        if self.trigger.trigger and self.trigger.trigger.type in [TriggerType.ON_SCAN_WITH_ITEM,
                                                                  TriggerType.ON_USE_ITEM]:
            self.item_label.grid(row=row, column=0)
            self.item_select.grid(row=row, column=1)
            row += 1
        else:
            self.item_label.grid_forget()
            self.item_select.grid_forget()

        self.actor_1_checkbox.grid(row=row, column=0, columnspan=2)
        row += 1
        self.actor_2_checkbox.grid(row=row, column=0, columnspan=2)
        row += 1
        self.actor_3_checkbox.grid(row=row, column=0, columnspan=2)
        row += 1
        self.living_actor_checkbox.grid(row=row, column=0, columnspan=2)
        row += 1
        self.callback_label.grid(row=row, column=0)
        self.callback_input.grid(row=row, column=1)
        row += 1

        if self.trigger.trigger and self.trigger.trigger.trigger_callback in self.functions:
            self.callback_actions_frame = self.configure_actions_frame(self.last_trigger_callback,
                                                                       self.trigger.trigger.trigger_callback,
                                                                       self.callback_actions_frame)
            self.last_trigger_callback = self.trigger.trigger.trigger_callback
            self.callback_actions_frame.grid(row=row, column=0, columnspan=2)
            row += 1
        elif self.callback_actions_frame is not None:
            self.callback_actions_frame.grid_forget()

    def configure_actions_frame(self, last_value: int, callback: int, frame: ttk.Labelframe | None,
                                show_return_value: bool = False) -> ttk.Labelframe:
        if callback != last_value or frame is None:
            if frame is not None:
                frame.grid_forget()
                frame.destroy()
            frame = self.make_action_frame(callback, show_return_value)
        return frame

    def on_change_id(self, *_):
        self.trigger.id = int(self.id_var.get() or '0')

    def on_change_enabled(self, *_):
        self.trigger.trigger.enabled_callback = int(self.enabled_var.get() or '0', 16)
        self.toggle_item()

    def on_change_condition(self, *_):
        self.trigger.trigger.type = TriggerType(self.conditions.index(self.condition_var.get()))
        self.toggle_item()

    def on_change_item(self, *_):
        self.trigger.trigger.item_id = KEY_ITEM_NAMES.index(self.item_var.get())

    def on_change_flag(self, flag: TriggerFlag, value: tk.BooleanVar):
        if value.get():
            self.trigger.trigger.flags |= flag
        else:
            self.trigger.trigger.flags &= ~flag

    def on_change_callback(self, *_):
        self.trigger.trigger.trigger_callback = int(self.callback_var.get() or '0', 16)
        self.toggle_item()

    def on_change_pos(self, axis: str):
        new_value = int(getattr(self, f'{axis}_var').get() or '0')
        setattr(self.trigger, f'{axis}_pos', Dimension(new_value, axis == 'x'))
        self.trigger.update_position()

    def on_change_size(self, dimension: str):
        var = getattr(self, f'{dimension}_var')
        var_dim = Dimension(int(var.get() or '0'), dimension == 'width')
        getattr(self.trigger, f'set_{dimension}')(var_dim)
        self.trigger.update()

    def on_object_transform(self, _):
        self.x_var.set_no_trace(str(self.trigger.x_pos.game_units))
        self.z_var.set_no_trace(str(self.trigger.z_pos.game_units))
        self.width_var.set_no_trace(str(self.trigger.width.game_units))
        self.height_var.set_no_trace(str(self.trigger.height.game_units))

    def destroy(self):
        self.trigger.remove_on_transform(self.on_object_transform)
        super().destroy()
