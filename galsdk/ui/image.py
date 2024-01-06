import tkinter as tk
import tkinter.filedialog as tkfile
from abc import ABCMeta, abstractmethod
from pathlib import Path
from tkinter import ttk
from typing import Literal

from PIL.Image import Image

from galsdk.ui.image_view import ImageView
from galsdk.ui.tab import Tab
from galsdk.project import Project
from galsdk.tim import TimFormat
from psx.tim import Tim


class ImageViewerTab(Tab, metaclass=ABCMeta):
    """Editor tab for viewing a series of images"""

    current_image: Tim | Image | None

    def __init__(self, name: str, project: Project, selectmode: Literal['extended', 'browse', 'none'] = 'browse',
                 show: Literal['tree', 'headings', 'tree headings', ''] = 'tree', supports_import: bool = False,
                 supports_insert: bool = False):
        super().__init__(name, project)

        self.context_ids = set()
        self.context_iid = None
        self.tree = ttk.Treeview(self, selectmode=selectmode, show=show)

        scroll = ttk.Scrollbar(self, command=self.tree.yview, orient='vertical')
        self.tree.configure(yscrollcommand=scroll.set)

        self.dimensions_var = tk.StringVar(self)
        self.bpp_var = tk.StringVar(self)

        self.image_view = ImageView(self)

        self.context_menu = tk.Menu(self, tearoff=False)
        if supports_import:
            self.context_menu.add_command(label='Import', command=self.on_import)
        self.context_menu.add_command(label='Export', command=self.on_export)
        if supports_insert:
            self.context_menu.add_separator()
            self.context_menu.add_command(label='Insert before', command=self.on_insert_before)
            self.context_menu.add_command(label='Insert after', command=self.on_insert_after)
            self.context_menu.add_command(label='Delete')

        self.tree.grid(row=0, column=0, rowspan=2, sticky=tk.NSEW)
        scroll.grid(row=0, column=1, rowspan=2, sticky=tk.NS)
        self.image_view.grid(row=0, column=2, sticky=tk.NSEW)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(2, weight=1)

        self.tree.bind('<<TreeviewSelect>>', self.on_selection_change)
        self.tree.bind('<<TreeviewOpen>>', self.on_node_open)
        self.tree.bind('<Button-3>', self.handle_right_click)

    def on_selection_change(self, _: tk.Event):
        self.image_view.image = self.get_image()
        self.context_menu.unpost()

    def handle_right_click(self, event: tk.Event):
        iid = self.tree.identify_row(event.y)
        if iid in self.context_ids and iid != self.context_iid:
            self.context_iid = iid
            self.context_menu.post(event.x_root, event.y_root)
        else:
            self.context_iid = None
            self.context_menu.unpost()

    def get_context_index(self) -> tuple[str, int]:
        parent_iid = self.tree.parent(self.context_iid)
        index = self.tree.index(self.context_iid)
        return parent_iid, index

    def on_insert(self, parent_iid: str, index: int):
        if not (image := self.get_image_from_iid(self.context_iid)):
            return

        extensions = ['*.png', '*.jpg', '*.bmp', '*.tga', '*.webp']
        if isinstance(image, Tim):
            extensions.append('*.tim')
        if filename := tkfile.askopenfilename(filetypes=[('Images', ' '.join(extensions)), ('All Files', '*.*')]):
            self.do_insert(Path(filename), parent_iid, index)
            self.image_view.image = self.get_image()

    def on_insert_before(self, *_):
        parent_iid, index = self.get_context_index()
        self.on_insert(parent_iid, index)

    def on_insert_after(self, *_):
        parent_iid, index = self.get_context_index()
        self.on_insert(parent_iid, index + 1)

    def on_delete(self, *_):
        self.do_delete(self.context_iid)

    def on_node_open(self, event: tk.Event):
        """Event handler when a tree node is opened; by default does nothing"""

    def on_export(self, *_):
        if not (image := self.get_image_from_iid(self.context_iid)):
            return

        extensions = '*.png *.jpg *.bmp *.tga *.webp'
        if is_tim := isinstance(image, Tim):
            extensions += ' *.tim'
        if filename := tkfile.asksaveasfilename(filetypes=[('Images', extensions), ('All Files', '*.*')]):
            path = Path(filename)
            if is_tim:
                tim = TimFormat.from_tim(image)
                tim.export(path, path.suffix)
            else:
                image.save(path)

    def on_import(self, *_):
        if not (image := self.get_image_from_iid(self.context_iid)):
            return

        extensions = ['*.png', '*.jpg', '*.bmp', '*.tga', '*.webp']
        if isinstance(image, Tim):
            extensions.append('*.tim')
        if filename := tkfile.askopenfilename(filetypes=[('Images', ' '.join(extensions)), ('All Files', '*.*')]):
            self.do_import(Path(filename), self.context_iid)
            self.image_view.image = self.get_image()

    def do_import(self, path: Path, iid: str):
        pass  # default does nothing for those that don't support it

    def do_insert(self, path: Path, parent_iid: str, index: int):
        pass  # default does nothing for those that don't support it

    def do_delete(self, iid: str):
        pass  # default does nothing for those that don't support it

    def get_image(self) -> Tim | Image | None:
        """Get the currently selected TIM image"""
        selection = self.tree.selection()
        if not selection:
            return None
        return self.get_image_from_iid(selection[0])

    @abstractmethod
    def get_image_from_iid(self, iid: str) -> Tim | Image | None:
        """Get the image for the given IID, if any"""
