import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

from PIL import ImageTk

from galsdk import graphics
from galsdk.game import Stage
from galsdk.manifest import FromManifest
from galsdk.project import Project
from galsdk.string import StringDb
from galsdk.ui.tab import Tab


@dataclass
class GameString:
    raw: bytes
    text: str
    stage_index: int
    source_db: FromManifest[StringDb]
    db_id: int


class StringTab(Tab):
    """Tab for viewing and editing text strings"""

    MAX_PREVIEW_LEN = 20

    current_index: int | None

    def __init__(self, project: Project):
        super().__init__('String', project)
        self.strings = []
        self.current_index = None
        self.font = project.get_font()
        self.dbs = {}
        self.changed_dbs = set()

        self.tree = ttk.Treeview(self, selectmode='browse', show='tree')
        scroll = ttk.Scrollbar(self, command=self.tree.yview, orient='vertical')
        self.tree.configure(yscrollcommand=scroll.set)

        for i, string_db in enumerate(project.get_unmapped_strings()):
            iid = f'unmapped_{i}'
            self.dbs[f'{string_db.manifest.name}/{string_db.file.name}'] = string_db
            self.tree.insert('', tk.END, text=string_db.file.name, iid=iid, open=False)
            for j, (raw, string) in string_db.obj.iter_both_ids():
                string_id = len(self.strings)
                self.strings.append(GameString(raw, string, 0, string_db, j))
                preview = f'{j}: {string}'
                if len(preview) > self.MAX_PREVIEW_LEN:
                    preview = preview[:self.MAX_PREVIEW_LEN - 3] + '...'
                self.tree.insert(iid, tk.END, text=preview, iid=str(string_id))

        for stage in Stage:
            stage: Stage
            self.tree.insert('', tk.END, text=f'Stage {stage}', iid=stage, open=False)

            stage_index = int(stage)
            string_db = project.get_stage_strings(stage)
            self.dbs[f'{string_db.manifest.name}/{string_db.file.name}'] = string_db
            for j, (raw, string) in string_db.obj.iter_both_ids():
                string_id = len(self.strings)
                self.strings.append(GameString(raw, string, stage_index, string_db, j))
                preview = f'{j}: {string}'
                if len(preview) > self.MAX_PREVIEW_LEN:
                    preview = preview[:self.MAX_PREVIEW_LEN-3] + '...'
                self.tree.insert(stage, tk.END, text=preview, iid=str(string_id))

        self.image_label = ttk.Label(self, compound='image', anchor=tk.CENTER)
        self.text_box = tk.Text(self)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(2, weight=1)

        self.tree.grid(row=0, column=0, rowspan=2, sticky=tk.NS + tk.W)
        scroll.grid(row=0, column=1, rowspan=2, sticky=tk.NS)
        self.image_label.grid(row=0, column=2, sticky=tk.N + tk.EW)
        self.text_box.grid(row=1, column=2, sticky=tk.S + tk.EW)

        self.tree.bind('<<TreeviewSelect>>', self.select_string)
        self.text_box.bind('<KeyRelease>', self.string_changed)
        self.image_label.bind('<Configure>', self.show)

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
            preview = f'* {string.db_id}: {string.text}'
            if len(preview) > self.MAX_PREVIEW_LEN:
                preview = preview[:self.MAX_PREVIEW_LEN - 3] + '...'
            self.tree.item(str(self.current_index), text=preview)
            db_index = db.get_index_from_id(string.db_id)
            db[db_index] = string.raw
            self.changed_dbs.add(f'{string.source_db.manifest.name}/{string.source_db.file.name}')
            self.notify_change()

    def select_string(self, _):
        try:
            index = int(self.tree.selection()[0])
        except ValueError:
            # not a string
            return

        if index != self.current_index:
            self.current_index = index
            string = self.strings[self.current_index]
            self.text_box.delete('1.0', tk.END)
            self.text_box.insert('1.0', string.text)
            self.show()

    @property
    def has_unsaved_changes(self) -> bool:
        return len(self.changed_dbs) > 0

    def save(self):
        for db_name in self.changed_dbs:
            db = self.dbs[db_name]
            db.save()
        self.changed_dbs.clear()
