import tkinter as tk
from tkinter import ttk

from PIL import ImageTk
from PIL.Image import Image

from psx.tim import Tim, Transparency


class ImageView(ttk.Frame):
    MIN_ZOOM = 0.5
    MAX_ZOOM = 3.

    def __init__(self, parent: tk.BaseWidget, image: Tim | Image | None = None):
        super().__init__(parent)
        self._image = image

        self.dimensions_var = tk.StringVar(self)
        self.label_var = tk.StringVar(self)

        self.image_label = ttk.Label(self, compound='image', anchor=tk.CENTER)
        self.clut_var = tk.StringVar(self, '0')
        self.transparency_var = tk.BooleanVar(self, True)
        clut_label = ttk.Label(self, text='CLUT:')
        self.clut_select = ttk.Combobox(self, textvariable=self.clut_var, state=tk.DISABLED)
        self.transparency_toggle = ttk.Checkbutton(self, text='Transparency', variable=self.transparency_var)
        self.zoom = ttk.Scale(self, from_=self.MIN_ZOOM, to=self.MAX_ZOOM, command=self.update_image, value=1.0)
        dimensions_label = ttk.Label(self, textvariable=self.dimensions_var)
        tim_label = ttk.Label(self, textvariable=self.label_var)

        self.transparency_var.trace_add('write', self.update_image)

        self.image_label.grid(row=0, column=0, sticky=tk.NSEW, columnspan=6)
        clut_label.grid(row=1, column=0, sticky=tk.SW)
        self.clut_select.grid(row=1, column=1, sticky=tk.SE)
        self.transparency_toggle.grid(padx=5, row=1, column=2, sticky=tk.SE)
        dimensions_label.grid(padx=5, row=1, column=3, sticky=tk.SE)
        tim_label.grid(padx=5, row=1, column=4, sticky=tk.SE)
        self.zoom.grid(padx=5, row=1, column=5, sticky=tk.S + tk.EW)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(5, weight=1)

        self.clut_select.bind('<<ComboboxSelected>>', self.update_image)

        self.image = image

    @property
    def image(self) -> Tim | Image | None:
        return self._image

    @image.setter
    def image(self, image: Tim | Image | None):
        self._image = image
        if not isinstance(self._image, Tim) or self._image.num_palettes == 0:
            self.clut_select['state'] = tk.DISABLED
        else:
            self.clut_select['state'] = 'readonly'
            self.clut_select['values'] = [str(i) for i in range(self._image.num_palettes)]
        self.clut_index = 0
        self.update_image()

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

    @with_transparency.setter
    def with_transparency(self, value: bool):
        self.transparency_var.set(value)

    def update_labels(self, *_):
        tim_label = ''
        if self._image is None:
            width = height = 0
        elif isinstance(self._image, Tim):
            tim_label = (
                f'BPP: {self._image.bpp.bpp}'
                f'  CLUT: {self._image.clut_x}, {self._image.clut_y}'
                f'  Image: {self._image.image_x}, {self._image.image_y}'
            )
            width = self._image.width
            height = self._image.height
        else:
            width, height = self._image.size
        self.dimensions_var.set(f'{width}x{height}')
        self.label_var.set(tim_label)

    def update_image(self, *_):
        self.update_labels()
        if self._image is not None:
            if isinstance(self._image, Tim):
                transparency = Transparency.FULL if self.with_transparency else Transparency.NONE
                image = self._image.to_image(self.clut_index, transparency)
            else:
                image = self._image
            zoom = self.zoom.get()
            if abs(zoom - 1) > 0.01:
                image = image.resize((int(image.size[0] * zoom), int(image.size[1] * zoom)))
            tk_image = ImageTk.PhotoImage(image)
        else:
            tk_image = None
        self.image_label.configure(image=tk_image)
        self.image_label.image = tk_image
