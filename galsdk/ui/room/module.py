import tkinter as tk
from tkinter import ttk

from galsdk.manifest import FromManifest
from galsdk.module import RoomModule
from galsdk.project import Map
from galsdk.ui.util import validate_int


class ModuleEditor(ttk.Frame):
    def __init__(self, module: FromManifest[RoomModule], maps: list[Map], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.module = module

        validator = (self.register(validate_int), '%P')

        index_label = ttk.Label(self, text='Index:', anchor=tk.W)
        index_value = ttk.Label(self, text=str(module.key))

        self.id_var = tk.StringVar(self, str(module.obj.module_id))
        self.id_var.trace_add('write', self.on_change_id)
        id_label = ttk.Label(self, text='ID:', anchor=tk.W)
        id_input = ttk.Entry(self, textvariable=self.id_var, validate='all', validatecommand=validator)

        map_labels = []
        entry_labels = []
        for map_ in maps:
            for room in map_.rooms:
                if room.module_index == module.key:
                    map_label = ttk.Label(self, text='Map/Room:', anchor=tk.W)
                    map_value = ttk.Label(self, text=f'{map_.index}/{room.room_index}')
                    entry_label = ttk.Label(self, text='Entry Point:', anchor=tk.W)
                    entry_value = ttk.Label(self, text=f'{room.entry_point:08X}')
                    map_labels.append((map_label, map_value))
                    entry_labels.append((entry_label, entry_value))

        # TODO: show entry point actions

        index_label.grid(row=0, column=0)
        index_value.grid(row=0, column=1)
        id_label.grid(row=1, column=0)
        id_input.grid(row=1, column=1)
        row = 2
        for (map_label, map_value), (entry_label, entry_value) in zip(map_labels, entry_labels, strict=True):
            map_label.grid(row=row, column=0)
            map_value.grid(row=row, column=1)
            row += 1
            entry_label.grid(row=row, column=0)
            entry_value.grid(row=row, column=1)
            row += 1

        id_input.focus_force()

    def on_change_id(self, *_):
        self.module.obj.module_id = int(self.id_var.get() or '0')
