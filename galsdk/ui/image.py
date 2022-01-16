import tkinter as tk
from abc import ABCMeta, abstractmethod
from tkinter import ttk
from typing import Literal, Optional

from PIL import ImageTk

from galsdk.ui.tab import Tab
from galsdk.project import Project
from psx.tim import Tim


class ImageViewerTab(Tab, metaclass=ABCMeta):
    """Editor tab for viewing a series of images"""

    current_image: Optional[Tim]

    def __init__(self, name: str, project: Project, selectmode: Literal['extended', 'browse', 'none'] = 'browse',
                 show: Literal['tree', 'headings', 'tree headings', ''] = 'tree'):
        super().__init__(name, project)

        self.current_image = None
        self.tree = ttk.Treeview(self, selectmode=selectmode, show=show)

        scroll = ttk.Scrollbar(self, command=self.tree.yview, orient='vertical')
        self.tree.configure(yscrollcommand=scroll.set)

        self.image_label = ttk.Label(self, compound='image', anchor=tk.CENTER)
        image_options = ttk.Frame(self)
        self.clut_var = tk.StringVar()
        self.transparency_var = tk.BooleanVar(value=True)
        clut_label = ttk.Label(image_options, text='CLUT:')
        self.clut_select = ttk.Combobox(image_options, textvariable=self.clut_var, state='disabled')
        transparency_toggle = ttk.Checkbutton(image_options, text='Transparency', variable=self.transparency_var,
                                              command=self.update_image)
        self.zoom = ttk.Scale(image_options, from_=0.5, to=2.0, command=self.update_image, value=1.0)
        clut_label.grid(row=0, column=0, sticky=tk.W)
        self.clut_select.grid(row=0, column=1, sticky=tk.E)
        transparency_toggle.grid(row=0, column=2, sticky=tk.E)
        self.zoom.grid(row=0, column=3, sticky=tk.E)

        self.tree.grid(row=0, column=0, rowspan=2, sticky=tk.NSEW)
        scroll.grid(row=0, column=1, rowspan=2, sticky=tk.NS)
        self.image_label.grid(row=0, column=2, sticky=tk.NSEW)
        image_options.grid(row=1, column=2, sticky=tk.S + tk.EW)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(2, weight=1)

        self.tree.bind('<<TreeviewSelect>>', self.on_selection_change)
        self.tree.bind('<<TreeviewOpen>>', self.on_node_open)
        self.clut_select.bind('<<ComboboxSelected>>', self.update_image)

    def on_selection_change(self, _: tk.Event):
        image = self.get_image()
        if image is not None:
            self.current_image = image
            if self.current_image.num_palettes == 0:
                self.clut_select['state'] = 'disabled'
            else:
                self.clut_select['state'] = 'readonly'
                self.clut_select['values'] = [str(i) for i in range(self.current_image.num_palettes)]
            self.clut_index = 0
            self.update_image()

    def on_node_open(self, event: tk.Event):
        """Event handler when a tree node is opened; by default does nothing"""

    @abstractmethod
    def get_image(self) -> Optional[Tim]:
        """Get the currently selected TIM image"""

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
            image = tim.to_image(self.clut_index, self.with_transparency)
            zoom = self.zoom.get()
            if abs(zoom - 1) > 0.01:
                image = image.resize((int(tim.width * zoom), int(tim.height * zoom)))
            tk_image = ImageTk.PhotoImage(image)
            self.image_label.configure(image=tk_image)
            self.image_label.image = tk_image
