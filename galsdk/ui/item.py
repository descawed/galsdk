import tkinter as tk
from tkinter import ttk

from direct.showbase.ShowBase import ShowBase
from PIL import ImageTk

from galsdk.project import Project
from galsdk.tile import TileSet
from galsdk.ui.model_viewer import ModelViewer
from galsdk.ui.tab import Tab
from psx.tim import Tim


class ItemTab(Tab):
    """Tab for viewing item art and info"""

    ICON_WIDTH = 32
    ICON_HEIGHT = 32

    def __init__(self, project: Project, base: ShowBase):
        super().__init__('Item', project)
        self.base = base
        self.items = []
        self.item_art = self.project.get_item_art()
        self.key_item_icons = []
        self.med_item_icons = []
        for mf in self.item_art:
            if mf.name.startswith('key_item_icons'):
                with self.item_art.get_first(mf.name).path.open('rb') as f:
                    self.key_item_icons.append(TileSet(Tim.read(f), self.ICON_WIDTH, self.ICON_HEIGHT))
            elif mf.name.startswith('medicine_icons'):
                with self.item_art.get_first(mf.name).path.open('rb') as f:
                    self.med_item_icons.append(TileSet(Tim.read(f), self.ICON_WIDTH, self.ICON_HEIGHT))
        # pre-load description images
        self.descriptions = []
        for description in self.item_art.iter_flat():
            if any(description.name.startswith(name) for name in ['key_item_icons', 'medicine_icons', 'ability_icons']):
                self.descriptions.append(None)  # just to keep the indexes the same
            else:
                with description.path.open('rb') as f:
                    self.descriptions.append(Tim.read(f))

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
            self.tree.insert(parent, tk.END, text=f'{item_id}: {item.name}', iid=str(item_id))

        self.model_frame = ModelViewer('item', self.base, 1280, 720, self)

        self.description_label = ttk.Label(self, compound='image', anchor=tk.CENTER)
        self.icon_label = ttk.Label(self, compound='image', anchor=tk.CENTER)

        self.tree.grid(row=0, column=0, rowspan=2, sticky=tk.NS + tk.W)
        scroll.grid(row=0, column=1, rowspan=2, sticky=tk.NS)
        self.model_frame.grid(row=0, column=2, columnspan=2, sticky=tk.NS + tk.E)
        self.description_label.grid(row=1, column=2, sticky=tk.SW)
        self.icon_label.grid(row=1, column=3, sticky=tk.SE)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(2, weight=1)
        self.grid_columnconfigure(3, weight=1)

        self.tree.bind('<<TreeviewSelect>>', self.select_item)
        self.bind('<Configure>', self.resize_3d)

    def resize_3d(self, _=None):
        self.update()
        x, y, width, height = self.grid_bbox(3, 0, 2, 0)
        self.model_frame.resize(width, height)

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

            # these icons are pretty small, so we scale them up
            desc_image = self.descriptions[item.description_index].to_image()
            width, height = desc_image.size
            desc_photo = ImageTk.PhotoImage(desc_image.resize((width * 2, height * 2)))
            self.description_label.configure(image=desc_photo)
            self.description_label.image = desc_photo

            if item.is_key_item:
                index = item.id
                for i, tile_set in enumerate(self.key_item_icons):
                    num_tiles = self.project.version.key_item_tile_counts[i]
                    if index < num_tiles:
                        icon_image = tile_set[index]
                        break
                    index -= num_tiles
                else:
                    raise KeyError(f'Could not find key item with ID {item.id}')
            else:
                icon_image = self.med_item_icons[0][item.id]
            width, height = icon_image.size
            icon_photo = ImageTk.PhotoImage(icon_image.resize((width * 2, height * 2)))
            self.icon_label.configure(image=icon_photo)
            self.icon_label.image = icon_photo

    def set_active(self, is_active: bool):
        self.model_frame.set_active(is_active)
        if is_active:
            self.resize_3d()

    def close(self):
        self.model_frame.close()
