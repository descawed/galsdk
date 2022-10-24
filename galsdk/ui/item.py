import tkinter as tk
from tkinter import ttk

from direct.showbase.ShowBase import ShowBase
from PIL import ImageTk

from galsdk.ui.model import ModelViewer
from galsdk.ui.tab import Tab
from galsdk.project import Project
from galsdk.tile import TileSet
from psx.tim import Tim


class ItemTab(Tab):
    """Tab for viewing item art and info"""

    ICON_WIDTH = 32
    ICON_HEIGHT = 32

    def __init__(self, project: Project, base: ShowBase):
        super().__init__('Items', project)
        self.base = base
        self.items = []
        self.item_art = self.project.get_item_art()
        with self.item_art['key_item_icons'].path.open('rb') as f:
            self.key_item_icons = TileSet(Tim.read(f), self.ICON_WIDTH, self.ICON_HEIGHT)
        with self.item_art['medicine_icons'].path.open('rb') as f:
            self.med_item_icons = TileSet(Tim.read(f), self.ICON_WIDTH, self.ICON_HEIGHT)
        # pre-load description images
        self.descriptions = []
        for description in self.item_art:
            if description.name not in ['key_item_icons', 'medicine_icons', 'ability_icons']:
                with description.path.open('rb') as f:
                    self.descriptions.append(Tim.read(f))
            else:
                self.descriptions.append(None)  # just to keep the indexes the same
        self.current_index = None

        self.tree = ttk.Treeview(self, selectmode='browse', show='tree')
        scroll = ttk.Scrollbar(self, command=self.tree.yview, orient='vertical')
        self.tree.configure(yscrollcommand=scroll.set)

        self.tree.insert('', tk.END, text='Key Items', iid='key')
        self.tree.insert('', tk.END, text='Medicine', iid='med')
        for item in self.project.get_items():
            item_id = len(self.items)
            self.items.append(item)
            parent = 'key' if item.is_key_item else 'med'
            self.tree.insert(parent, tk.END, text=item.name, iid=str(item_id))

        self.model_frame = ModelViewer('item', self.base, 1280, 720, self)

        self.description_label = ttk.Label(self, compound='image', anchor=tk.CENTER)
        self.icon_label = ttk.Label(self, compound='image', anchor=tk.CENTER)

        self.tree.grid(row=0, column=0, rowspan=2, sticky=tk.NS + tk.W)
        scroll.grid(row=0, column=1, rowspan=2, sticky=tk.NS)
        self.model_frame.grid(row=0, column=2, columnspan=2, sticky=tk.NS + tk.E)
        self.description_label.grid(row=1, column=2, sticky=tk.SW)
        self.icon_label.grid(row=1, column=3, sticky=tk.SE)

        self.grid_columnconfigure(2, weight=1)
        self.grid_columnconfigure(3, weight=1)

        self.tree.bind('<<TreeviewSelect>>', self.select_item)

    def select_item(self, _):
        try:
            index = int(self.tree.selection()[0])
        except ValueError:
            # not an item
            return

        if index != self.current_index:
            self.current_index = index
            item = self.items[index]
            self.model_frame.set_model(item.model)

            desc_image = ImageTk.PhotoImage(self.descriptions[item.description_index].to_image())
            self.description_label.configure(image=desc_image)
            self.description_label.image = desc_image

            source = self.key_item_icons if item.is_key_item else self.med_item_icons
            icon_image = ImageTk.PhotoImage(source[item.id])
            self.icon_label.configure(image=icon_image)
            self.icon_label.image = icon_image

    def set_active(self, is_active: bool):
        self.model_frame.set_active(is_active)
