import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

from PIL import ImageTk

from galsdk import util
from galsdk.ui.tab import Tab
from galsdk.project import Project
from galsdk.game import Stage
from galsdk.string import StringDb


@dataclass
class GameString:
    raw: bytes
    text: str
    stage_index: int
    source_db: StringDb


class StringTab(Tab):
    """Tab for viewing and editing text strings"""

    MAX_PREVIEW_LEN = 20

    current_index: int | None

    def __init__(self, project: Project):
        super().__init__('String', project)
        self.strings = []
        self.current_index = None
        self.font = project.get_font()

        self.tree = ttk.Treeview(self, selectmode='browse', show='tree')
        scroll = ttk.Scrollbar(self, command=self.tree.yview, orient='vertical')
        self.tree.configure(yscrollcommand=scroll.set)

        for i, (name, string_db) in enumerate(project.get_unmapped_strings()):
            iid = f'unmapped_{i}'
            self.tree.insert('', tk.END, text=name, iid=iid, open=False)
            for j, (raw, string) in enumerate(string_db.iter_both()):
                string_id = len(self.strings)
                self.strings.append(GameString(raw, string, 0, string_db))
                preview = f'{j}: {string}'
                if len(preview) > self.MAX_PREVIEW_LEN:
                    preview = preview[:self.MAX_PREVIEW_LEN - 3] + '...'
                self.tree.insert(iid, tk.END, text=preview, iid=str(string_id))

        for i, stage in enumerate(Stage):
            stage: Stage
            self.tree.insert('', tk.END, text=f'Stage {stage}', iid=stage, open=False)

            string_db = project.get_stage_strings(stage)
            for j, (raw, string) in enumerate(string_db.iter_both()):
                string_id = len(self.strings)
                self.strings.append(GameString(raw, string, i, string_db))
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
        new_size = util.scale_to_fit(original_width, original_height, available_width, available_height, 3)

        pil_image = pil_image.resize(new_size)
        tk_image = ImageTk.PhotoImage(pil_image)
        self.image_label.configure(image=tk_image)
        self.image_label.image = tk_image

    def string_changed(self, _=None):
        text = self.text_box.get('1.0', tk.END).strip('\n')
        string = self.strings[self.current_index]
        try:
            string.raw = string.source_db.encode(text, string.stage_index)
            self.show()
        except (IndexError, ValueError):
            pass  # user is probably editing

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
