import tkinter as tk
import tkinter.filedialog as tkfile
from abc import ABCMeta, abstractmethod
from pathlib import Path
from tkinter import ttk
from typing import Literal

from PIL import ImageTk
from PIL.Image import Image

from galsdk.ui.tab import Tab
from galsdk.project import Project
from galsdk.tim import TimFormat
from psx.tim import BitsPerPixel, Tim, Transparency


class ImageViewerTab(Tab, metaclass=ABCMeta):
    """Editor tab for viewing a series of images"""

    current_image: Tim | Image | None

    def __init__(self, name: str, project: Project, selectmode: Literal['extended', 'browse', 'none'] = 'browse',
                 show: Literal['tree', 'headings', 'tree headings', ''] = 'tree', supports_import: bool = False):
        super().__init__(name, project)

        self.current_image = None
        self.context_ids = set()
        self.context_iid = None
        self.tree = ttk.Treeview(self, selectmode=selectmode, show=show)

        scroll = ttk.Scrollbar(self, command=self.tree.yview, orient='vertical')
        self.tree.configure(yscrollcommand=scroll.set)

        self.dimensions_var = tk.StringVar(self)
        self.bpp_var = tk.StringVar(self)

        self.image_label = ttk.Label(self, compound='image', anchor=tk.CENTER)
        image_options = ttk.Frame(self)
        self.clut_var = tk.StringVar()
        self.transparency_var = tk.BooleanVar(value=True)
        clut_label = ttk.Label(image_options, text='CLUT:')
        self.clut_select = ttk.Combobox(image_options, textvariable=self.clut_var, state='disabled')
        transparency_toggle = ttk.Checkbutton(image_options, text='Transparency', variable=self.transparency_var,
                                              command=self.update_image)
        self.zoom = ttk.Scale(image_options, from_=0.5, to=3.0, command=self.update_image, value=1.0)
        dimensions_label = ttk.Label(image_options, textvariable=self.dimensions_var)
        bpp_label = ttk.Label(image_options, textvariable=self.bpp_var)
        clut_label.grid(row=0, column=0, sticky=tk.W)
        self.clut_select.grid(row=0, column=1, sticky=tk.E)
        transparency_toggle.grid(padx=5, row=0, column=2, sticky=tk.E)
        dimensions_label.grid(padx=5, row=0, column=3, sticky=tk.E)
        bpp_label.grid(padx=5, row=0, column=4, sticky=tk.E)
        self.zoom.grid(padx=5, row=0, column=5, sticky=tk.EW)
        image_options.grid_columnconfigure(5, weight=1)

        self.context_menu = tk.Menu(self, tearoff=False)
        if supports_import:
            self.context_menu.add_command(label='Import', command=self.on_import)
        self.context_menu.add_command(label='Export', command=self.on_export)

        self.tree.grid(row=0, column=0, rowspan=2, sticky=tk.NSEW)
        scroll.grid(row=0, column=1, rowspan=2, sticky=tk.NS)
        self.image_label.grid(row=0, column=2, sticky=tk.NSEW)
        image_options.grid(row=1, column=2, sticky=tk.S + tk.EW)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(2, weight=1)

        self.tree.bind('<<TreeviewSelect>>', self.on_selection_change)
        self.tree.bind('<<TreeviewOpen>>', self.on_node_open)
        self.tree.bind('<Button-3>', self.handle_right_click)
        self.clut_select.bind('<<ComboboxSelected>>', self.update_image)

    def on_selection_change(self, _: tk.Event):
        image = self.get_image()
        if image is not None:
            self.current_image = image
            if not isinstance(self.current_image, Tim) or self.current_image.num_palettes == 0:
                self.clut_select['state'] = 'disabled'
            else:
                self.clut_select['state'] = 'readonly'
                self.clut_select['values'] = [str(i) for i in range(self.current_image.num_palettes)]
            self.clut_index = 0
            self.update_image()

    def handle_right_click(self, event: tk.Event):
        iid = self.tree.identify_row(event.y)
        if iid in self.context_ids and iid != self.context_iid:
            self.context_iid = iid
            self.context_menu.post(event.x_root, event.y_root)
        else:
            self.context_iid = None
            self.context_menu.unpost()

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
            self.update_image()

    def do_import(self, path: Path, iid: str):
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

    @property
    def clut_index(self) -> int:
        try:
            return int(self.clut_var.get())
        except ValueError:
            return 0

    @clut_index.setter
    def clut_index(self, value: int):
        self.clut_var.set(str(value))

    @property
    def with_transparency(self) -> bool:
        return self.transparency_var.get()

    def update_image(self, *_):
        tim = self.get_image()
        if tim is not None:
            bpp_label = ''
            if isinstance(tim, Tim):
                transparency = Transparency.FULL if self.with_transparency else Transparency.NONE
                image = tim.to_image(self.clut_index, transparency)
                bpp_label = 'BPP: '
                match tim.bpp:
                    case BitsPerPixel.BPP_4:
                        bpp_label += '4'
                    case BitsPerPixel.BPP_8:
                        bpp_label += '8'
                    case BitsPerPixel.BPP_16:
                        bpp_label += '16'
                    case _:
                        bpp_label += '24'
            else:
                image = tim
            width, height = image.size
            self.dimensions_var.set(f'{width}x{height}')
            self.bpp_var.set(bpp_label)
            zoom = self.zoom.get()
            if abs(zoom - 1) > 0.01:
                image = image.resize((int(image.size[0] * zoom), int(image.size[1] * zoom)))
            tk_image = ImageTk.PhotoImage(image)
            self.image_label.configure(image=tk_image)
            self.image_label.image = tk_image
