import tkinter as tk
from tkinter import ttk

from PIL import ImageTk
from PIL.Image import Image

from psx.tim import BitsPerPixel, Tim, Transparency


class ImageView(ttk.Frame):
    def __init__(self, parent: tk.BaseWidget, image: Tim | Image | None = None):
        super().__init__(parent)
        self._image = image

        self.dimensions_var = tk.StringVar(self)
        self.bpp_var = tk.StringVar(self)

        self.image_label = ttk.Label(self, compound='image', anchor=tk.CENTER)
        self.clut_var = tk.StringVar(self, '0')
        self.transparency_var = tk.BooleanVar(self, True)
        clut_label = ttk.Label(self, text='CLUT:')
        self.clut_select = ttk.Combobox(self, textvariable=self.clut_var, state=tk.DISABLED)
        self.transparency_toggle = ttk.Checkbutton(self, text='Transparency', variable=self.transparency_var,
                                                   command=self.update_image)
        self.zoom = ttk.Scale(self, from_=0.5, to=3.0, command=self.update_image, value=1.0)
        dimensions_label = ttk.Label(self, textvariable=self.dimensions_var)
        bpp_label = ttk.Label(self, textvariable=self.bpp_var)

        self.image_label.grid(row=0, column=0, sticky=tk.NSEW, columnspan=6)
        clut_label.grid(row=1, column=0, sticky=tk.W)
        self.clut_select.grid(row=1, column=1, sticky=tk.E)
        self.transparency_toggle.grid(padx=5, row=1, column=2, sticky=tk.E)
        dimensions_label.grid(padx=5, row=1, column=3, sticky=tk.E)
        bpp_label.grid(padx=5, row=1, column=4, sticky=tk.E)
        self.zoom.grid(padx=5, row=1, column=5, sticky=tk.EW)

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

    def update_image(self, *_):
        if self._image is not None:
            bpp_label = ''
            if isinstance(self._image, Tim):
                transparency = Transparency.FULL if self.with_transparency else Transparency.NONE
                image = self._image.to_image(self.clut_index, transparency)
                bpp_label = 'BPP: '
                match self._image.bpp:
                    case BitsPerPixel.BPP_4:
                        bpp_label += '4'
                    case BitsPerPixel.BPP_8:
                        bpp_label += '8'
                    case BitsPerPixel.BPP_16:
                        bpp_label += '16'
                    case _:
                        bpp_label += '24'
            else:
                image = self._image
            width, height = image.size
            self.dimensions_var.set(f'{width}x{height}')
            self.bpp_var.set(bpp_label)
            zoom = self.zoom.get()
            if abs(zoom - 1) > 0.01:
                image = image.resize((int(image.size[0] * zoom), int(image.size[1] * zoom)))
            tk_image = ImageTk.PhotoImage(image)
        else:
            tk_image = None
        self.image_label.configure(image=tk_image)
        self.image_label.image = tk_image
