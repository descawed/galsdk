import tkinter as tk
import tkinter.filedialog as tkfile
import tkinter.messagebox as tkmsg
import tkinter.simpledialog as tksimple
from pathlib import Path
from tkinter import ttk

from galsdk.manifest import Manifest
from galsdk.module import RoomModule
from galsdk.project import Map, Project
from galsdk.ui.util import validate_int


class MapEditor(tk.Toplevel):
    modules_added: dict[int, tuple[Path, RoomModule]]

    def __init__(self, maps: list[Map], module_manifest: Manifest, project: Project, parent: tk.Tk,
                 *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.title('Map Editor')
        self.transient(parent)
        self.confirmed = False

        self.maps = maps
        self.module_manifest = module_manifest
        self.project = project
        self.modules_added = {}
        # the same module can appear in the list more than once, but the entry point should be the same each time
        self.known_entry_points = {room.module_index: room.entry_point for map_ in maps for room in map_.rooms}

        hex_validator = (self.register(lambda s: validate_int(s, 16)), '%P')

        self.module_var = tk.StringVar(self)
        self.module_var.trace_add('write', self.update_module)
        self.entry_var = tk.StringVar(self)
        self.entry_var.trace_add('write', self.update_entry_point)

        self.tree = ttk.Treeview(self, selectmode='browse', show='tree')
        scroll = ttk.Scrollbar(self, command=self.tree.yview, orient='vertical')
        self.tree.configure(yscrollcommand=scroll.set)

        for map_ in self.maps:
            map_iid = str(map_.index)
            self.tree.insert('', tk.END, map_iid, text=f'{map_.index}: {map_.name}')
            for room in map_.rooms:
                mf = self.module_manifest[room.module_index]
                self.tree.insert(map_iid, tk.END, f'{map_.index}_{room.room_index}',
                                 text=f'{room.room_index}: {mf.name}')

        input_frame = ttk.Frame(self)
        module_label = ttk.Label(input_frame, text='Module:', anchor=tk.W)
        self.module_select = ttk.Combobox(input_frame, values=self.module_options, textvariable=self.module_var,
                                          state=tk.DISABLED)
        self.browse_button = ttk.Button(input_frame, text='...', state=tk.DISABLED, command=self.browse_module)
        entry_label = ttk.Label(input_frame, text='Entry Point:', anchor=tk.W)
        self.entry_entry = ttk.Entry(input_frame, textvariable=self.entry_var, validate='all',
                                     validatecommand=hex_validator, state=tk.DISABLED)

        ok_button = ttk.Button(self, text='OK', command=self.on_ok)
        cancel_button = ttk.Button(self, text='Cancel', command=self.on_cancel)

        module_label.grid(row=0, column=0, sticky=tk.W)
        self.module_select.grid(row=0, column=1, sticky=tk.EW)
        self.browse_button.grid(row=0, column=2, sticky=tk.E, padx=5)
        entry_label.grid(row=1, column=0, sticky=tk.W)
        self.entry_entry.grid(row=1, column=1, columnspan=2, sticky=tk.EW)

        self.tree.grid(row=0, column=0, sticky=tk.NSEW)
        scroll.grid(row=0, column=1, sticky=tk.NS)
        input_frame.grid(row=0, column=2)
        ok_button.grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        cancel_button.grid(row=1, column=2, sticky=tk.E, padx=5, pady=5)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.tree.bind('<<TreeviewSelect>>', self.on_select)
        self.bind('WM_DELETE_WINDOW', self.on_cancel)

        x = parent.winfo_rootx()
        y = parent.winfo_rooty()
        width = parent.winfo_width()
        dialog_width = 700
        dialog_x = x + width // 2 - dialog_width // 2
        self.geometry(f'{dialog_width}x800+{dialog_x}+{y}')

        self.wait_visibility()
        self.grab_set()
        self.wait_window(self)

    def update_module(self, *_):
        module_index = self.selected_module_index
        map_index, room_index = self.selected_item
        self.maps[map_index].rooms[room_index].module_index = module_index
        if module_index in self.known_entry_points:
            self.entry_var.set(f'{self.known_entry_points[module_index]:08X}')

    def update_entry_point(self, *_):
        entry_point = int(self.entry_entry.get() or '0', 16)
        map_index, room_index = self.selected_item
        self.maps[map_index].rooms[room_index].entry_point = entry_point

    def on_ok(self, *_):
        self.confirmed = True
        final_modules_added = {}
        for index, (path, module) in self.modules_added.items():
            name = self.module_manifest.get_unique_name(module.name)
            final_index = len(self.module_manifest)
            mf = self.module_manifest.add(path, name=name)
            with mf.path.with_suffix('.json').open('w') as f:
                module.save_metadata(f)
            # in case the manifest was modified after we came up with the initial index, rebuild the dictionary
            final_modules_added[final_index] = (path, module)
        self.modules_added = final_modules_added
        self.destroy()

    def on_cancel(self, *_):
        self.confirmed = False
        self.destroy()

    def ask_entry_point(self, start_address: int, end_address: int) -> int | None:
        entry_point = None
        while entry_point is None or entry_point < start_address or entry_point >= end_address:
            address = tksimple.askstring('Entry Point', 'Address:', parent=self)
            if address is None:
                return None  # user cancelled

            try:
                entry_point = int(address, 16)
            except ValueError:
                tkmsg.showerror('Invalid address', f'{address} is not a valid hexadecimal number', parent=self)
                continue

            if entry_point < start_address or entry_point >= end_address:
                tkmsg.showerror('Invalid address',
                                f"{address} is not in the module's address space "
                                f'({start_address:08X}-{end_address:08X})',
                                parent=self)

        return entry_point

    def browse_module(self, *_):
        filename = tkfile.askopenfilename(filetypes=[('All Files', '*.*')], parent=self)
        if not filename:
            return

        path = Path(filename)
        size = path.stat().st_size
        if size > RoomModule.MAX_MODULE_SIZE:
            confirm = tkmsg.askyesno('Module too large',
                                     'This module is larger than the size reserved in memory for room modules.'
                                     ' The game will likely crash or experience instability when loading this module.'
                                     ' Are you sure you want to continue?', icon=tkmsg.WARNING, parent=self)
            if not confirm:
                return

        if path.with_suffix('.json').exists():
            # this module already has metadata
            try:
                module = RoomModule.load_with_metadata(path, self.project.version.id)
            except Exception as e:
                tkmsg.showerror('Module load failed', str(e), parent=self)
                return
        else:
            # this module does not have metadata. at a minimum, we need the entry point.
            start_address = self.project.addresses['ModuleLoadAddresses'][0]
            end_address = start_address + size

            entry_point = self.ask_entry_point(start_address, end_address)
            if entry_point is None:
                return

            with path.open('rb') as f:
                try:
                    module = RoomModule.read(f, version=self.project.version.id, entry_point=entry_point)
                except Exception as e:
                    tkmsg.showerror('Module load failed', str(e), parent=self)
                    return

        # we won't actually insert into the manifest until the user presses OK
        new_index = len(self.module_manifest)
        while new_index in self.modules_added:
            new_index += 1

        self.modules_added[new_index] = (path, module)
        self.module_select.configure(values=self.module_options)
        name = self.module_manifest.get_unique_name(module.name)
        self.module_var.set(f'{new_index}: {name}')
        self.entry_var.set(f'{module.entry_point:08X}')

    @property
    def module_options(self) -> list[str]:
        out = [f'{i}: {mf.name}' for i, mf in enumerate(self.module_manifest)]
        for index, (_, module) in self.modules_added.items():
            name = self.module_manifest.get_unique_name(module.name)
            out.append(f'{index}: {name}')
        return out

    @property
    def selected_module_index(self) -> int | None:
        if self.module_select['state'] == tk.DISABLED:
            return None
        return int(self.module_var.get().split(':', 1)[0])

    @property
    def selected_item(self) -> tuple[int | None, int | None]:
        map_index = room_index = None
        if selection := self.tree.selection():
            pieces = selection[0].split('_')
            map_index = int(pieces[0])
            if len(pieces) > 1:
                room_index = int(pieces[1])
        return map_index, room_index

    def on_select(self, *_):
        map_index, room_index = self.selected_item
        if room_index is None:
            self.module_select.configure(state=tk.DISABLED)
            self.browse_button.configure(state=tk.DISABLED)
            self.entry_entry.configure(state=tk.DISABLED)
        else:
            room = self.maps[map_index].rooms[room_index]
            mf = self.module_manifest[room.module_index]
            self.module_var.set(f'{room.module_index}: {mf.name}')
            self.entry_var.set(f'{room.entry_point:08X}')
            self.module_select.configure(state='readonly')
            self.browse_button.configure(state=tk.NORMAL)
            self.entry_entry.configure(state=tk.NORMAL)
