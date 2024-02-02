import itertools
import tkinter as tk
import tkinter.filedialog as tkfile
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk

from PIL import ImageTk

from galsdk import graphics
from galsdk.game import Stage
from galsdk.manifest import FromManifest
from galsdk.project import Project
from galsdk.string import StringDb
from galsdk.ui.tab import Tab
from galsdk.ui.util import get_preview_string


@dataclass
class GameString:
    raw: bytes
    text: str
    stage_index: int
    source_db: FromManifest[StringDb]
    db_id: int


class StringTab(Tab):
    """Tab for viewing and editing text strings"""

    current_index: int | None
    strings: list[GameString | None]

    def __init__(self, project: Project):
        super().__init__('String', project)
        self.strings = []
        self.current_index = None
        self.font = project.get_font()
        self.dbs = {}
        self.db_iid_map = {}
        self.changed_dbs = set()

        self.tree = ttk.Treeview(self, selectmode='browse', show='tree')
        scroll = ttk.Scrollbar(self, command=self.tree.yview, orient='vertical')
        self.tree.configure(yscrollcommand=scroll.set)

        self.context_menu = tk.Menu(self, tearoff=False)
        self.context_menu.add_command(label='Insert before', command=self.insert_before)
        self.context_menu.add_command(label='Insert after', command=self.insert_after)
        self.context_menu.add_separator()
        self.context_menu.add_command(label='Delete', command=self.delete)
        self.context_index = None

        self.db_context_menu = tk.Menu(self, tearoff=False)
        self.db_context_menu.add_command(label='Import', command=self.on_import)
        self.db_context_menu.add_command(label='Export', command=self.on_export)
        self.db_context_iid = None

        for i, string_db in enumerate(project.get_unmapped_strings()):
            iid = f'unmapped_{i}'
            self.dbs[f'{string_db.manifest.name}/{string_db.file.name}'] = string_db
            self.db_iid_map[iid] = string_db
            self.tree.insert('', tk.END, text=string_db.file.name, iid=iid, open=False)
            for j, (raw, string) in string_db.obj.iter_both_ids():
                string_id = len(self.strings)
                self.strings.append(GameString(raw, string, 0, string_db, j))
                preview = get_preview_string(f'{j}: {string}')
                self.tree.insert(iid, tk.END, text=preview, iid=str(string_id))

        for stage in Stage:
            stage: Stage
            self.tree.insert('', tk.END, text=f'Stage {stage}', iid=stage, open=False)

            stage_index = int(stage)
            string_db = project.get_stage_strings(stage)
            self.dbs[f'{string_db.manifest.name}/{string_db.file.name}'] = string_db
            self.db_iid_map[stage] = string_db
            for j, (raw, string) in string_db.obj.iter_both_ids():
                string_id = len(self.strings)
                self.strings.append(GameString(raw, string, stage_index, string_db, j))
                preview = get_preview_string(f'{j}: {string}')
                self.tree.insert(stage, tk.END, text=preview, iid=str(string_id))

        self.image_label = ttk.Label(self, compound='image', anchor=tk.CENTER)
        self.text_box = tk.Text(self, state=tk.DISABLED)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(2, weight=1)

        self.tree.grid(row=0, column=0, rowspan=2, sticky=tk.NS + tk.W)
        scroll.grid(row=0, column=1, rowspan=2, sticky=tk.NS)
        self.image_label.grid(row=0, column=2, sticky=tk.N + tk.EW)
        self.text_box.grid(row=1, column=2, sticky=tk.S + tk.EW)

        self.tree.bind('<<TreeviewSelect>>', self.select_string)
        self.tree.bind('<Button-3>', self.handle_right_click)
        self.text_box.bind('<KeyRelease>', self.string_changed)
        self.image_label.bind('<Configure>', self.show)

    def insert(self, offset: int):
        info = self.strings[self.context_index]
        relative_index = info.source_db.obj.get_index_from_id(info.db_id)
        ui_index = len(self.strings)
        db_index = relative_index + offset
        string_id = info.source_db.obj.insert(db_index, '')
        self.strings.append(GameString(b'', '', info.stage_index, info.source_db, string_id))
        self.changed_dbs.add(f'{info.source_db.manifest.name}/{info.source_db.file.name}')
        self.notify_change()

        parent = self.tree.parent(str(self.context_index))
        iid = str(ui_index)
        self.tree.insert(parent, db_index, iid, text=f'* {string_id}: ')
        self.update_ids(parent, info.source_db.obj)
        self.tree.selection_set(iid)
        self.text_box.focus_set()

    def update_ids(self, parent_iid: str, db: StringDb):
        for (iid, (db_id, _)) in zip(self.tree.get_children(parent_iid), db.iter_ids(), strict=True):
            label = self.tree.item(iid, 'text')
            id_part, preview_part = label.split(':', 1)
            marker = '* ' if id_part.startswith('* ') else ''
            self.tree.item(iid, text=f'{marker}{db_id}:{preview_part}')
            self.strings[int(iid)].db_id = db_id

    def insert_before(self, *_):
        self.insert(0)

    def insert_after(self, *_):
        self.insert(1)

    def delete(self, *_):
        iid = str(self.context_index)
        parent = self.tree.parent(iid)
        info = self.strings[self.context_index]
        self.strings[self.context_index] = None
        self.tree.delete(iid)
        db_index = info.source_db.obj.get_index_from_id(info.db_id)
        del info.source_db.obj[db_index]
        if self.current_index == self.context_index:
            self.current_index = None
            self.text_box.delete('1.0', tk.END)
            self.text_box.configure(state=tk.DISABLED)
        self.update_ids(parent, info.source_db.obj)
        self.changed_dbs.add(f'{info.source_db.manifest.name}/{info.source_db.file.name}')
        self.notify_change()

    def on_export(self, *_):
        filename = tkfile.asksaveasfilename(defaultextension='.txt', filetypes=[('Text', '*.txt'), ('All Files', '*.*')])
        if filename is None:
            return

        self.db_iid_map[self.db_context_iid].obj.export(Path(filename))

    def on_import(self, *_):
        filename = tkfile.askopenfilename(defaultextension='.txt', filetypes=[('Text', '*.txt'), ('All Files', '*.*')])
        if filename is None:
            return

        info = self.db_iid_map[self.db_context_iid]
        db = info.obj
        old_strings = list(db)
        db.import_in_place(Path(filename))
        for child in self.tree.get_children(self.db_context_iid):
            self.strings[int(child)] = None
        self.tree.set_children(self.db_context_iid)
        any_changed = False
        for new_info, old_string in itertools.zip_longest(db.iter_both_ids(), old_strings):
            if new_info is None:
                if old_string is not None:
                    any_changed = True  # we got shorter
                break

            new_id, (raw_string, new_string) = new_info
            ui_index = len(self.strings)
            if new_string != old_string:
                any_changed = True
                marker = '* '
            else:
                marker = ''
            preview = get_preview_string(f'{new_id}: {new_string}')
            self.tree.insert(self.db_context_iid, tk.END, str(ui_index), text=f'{marker}{preview}')
            try:
                stage_index = int(Stage(self.db_context_iid))
            except ValueError:
                stage_index = 0
            self.strings.append(GameString(raw_string, new_string, stage_index, info, new_id))

        if any_changed:
            self.changed_dbs.add(f'{info.manifest.name}/{info.file.name}')
            self.notify_change()

    def handle_right_click(self, event: tk.Event):
        self.context_menu.unpost()
        self.context_index = None
        self.db_context_menu.unpost()
        self.db_context_iid = None

        iid = self.tree.identify_row(event.y)
        if self.tree.get_children(iid):
            self.db_context_iid = iid
            self.db_context_menu.post(event.x_root, event.y_root)
        else:
            self.context_index = int(iid)
            self.context_menu.post(event.x_root, event.y_root)

    def show(self, *_):
        if self.current_index is None:
            return

        string = self.strings[self.current_index]
        try:
            pil_image = self.font.draw(string.raw, string.stage_index)
        except (ValueError, KeyError):
            return  # if the text is invalid, just ignore it; the user might be in the middle of changing it

        # resize the image to fill the available space
        x, y, available_width, available_height = self.grid_bbox(2, 0)
        original_width, original_height = pil_image.size
        new_size = graphics.scale_to_fit(original_width, original_height, available_width, available_height, 3)

        pil_image = pil_image.resize(new_size)
        tk_image = ImageTk.PhotoImage(pil_image)
        self.image_label.configure(image=tk_image)
        self.image_label.image = tk_image

    def string_changed(self, _=None):
        if self.current_index is None:
            return

        text = self.text_box.get('1.0', tk.END).strip('\n')
        string = self.strings[self.current_index]
        if text != string.text:
            try:
                db = string.source_db.obj
                string.raw = db.encode(text, string.stage_index)
                self.show()
            except (IndexError, ValueError):
                return  # user is probably editing

            string.text = text
            preview = get_preview_string(f'* {string.db_id}: {string.text}')
            iid = str(self.current_index)
            self.tree.item(iid, text=preview)
            db_index = db.get_index_from_id(string.db_id)
            db[db_index] = string.raw
            self.changed_dbs.add(f'{string.source_db.manifest.name}/{string.source_db.file.name}')
            self.notify_change()
            self.update_ids(self.tree.parent(iid), db)

    def select_string(self, _):
        self.context_menu.unpost()
        self.db_context_menu.unpost()
        try:
            index = int(self.tree.selection()[0])
        except (ValueError, IndexError):
            # not a string or nothing selected
            return

        self.text_box.configure(state=tk.NORMAL)
        if index != self.current_index:
            self.current_index = index
            string = self.strings[self.current_index]
            self.text_box.delete('1.0', tk.END)
            self.text_box.insert('1.0', string.text)
            self.show()

    def clear_change_markers(self, parent_iid: str = ''):
        label = self.tree.item(parent_iid, 'text')
        if label.startswith('* '):
            self.tree.item(parent_iid, text=label[2:])

        for child in self.tree.get_children(parent_iid):
            self.clear_change_markers(child)

    @property
    def has_unsaved_changes(self) -> bool:
        return len(self.changed_dbs) > 0

    def save(self):
        for db_name in self.changed_dbs:
            db = self.dbs[db_name]
            db.save()
        self.changed_dbs.clear()
        self.clear_change_markers()
