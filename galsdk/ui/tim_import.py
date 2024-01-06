import tkinter as tk
from tkinter import ttk

import PIL.features
from PIL import Image

from galsdk.ui.image_view import ImageView
from galsdk.ui.util import validate_int
from psx.tim import BitsPerPixel, Tim


class TimImportDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk, image: Image.Image):
        super().__init__(parent)
        self.transient(parent)

        self.title('TIM Import')
        self.input_image = image
        quantization_methods = self.quantization_methods
        default_method = 'Median cut' if 'Median cut' in quantization_methods else 'Fast octree'

        validator = (self.register(validate_int), '%P')

        self.bpp_var = tk.StringVar(self, '24')
        self.clut_x_var = tk.StringVar(self, '0')
        self.clut_y_var = tk.StringVar(self, '0')
        self.image_x_var = tk.StringVar(self, '0')
        self.image_y_var = tk.StringVar(self, '0')
        self.quant_var = tk.StringVar(self, default_method)
        self.dither_var = tk.BooleanVar(self, True)

        # x/y positions don't affect the preview, so we won't update the image when they change
        self.bpp_var.trace_add('write', self.update_image)
        self.quant_var.trace_add('write', self.update_image)
        self.dither_var.trace_add('write', self.update_image)

        self.output_tim = self.to_tim()

        bpp_label = ttk.Label(self, text='BPP:', anchor=tk.W)
        bpp_select = ttk.Combobox(self, textvariable=self.bpp_var, values=['4', '8', '16', '24'])

        clut_x_label = ttk.Label(self, text='CLUT X:', anchor=tk.W)
        clut_x_entry = ttk.Entry(self, textvariable=self.clut_x_var, validate='all', validatecommand=validator)

        clut_y_label = ttk.Label(self, text='CLUT Y:', anchor=tk.W)
        clut_y_entry = ttk.Entry(self, textvariable=self.clut_y_var, validate='all', validatecommand=validator)

        image_x_label = ttk.Label(self, text='Image X:', anchor=tk.W)
        image_x_entry = ttk.Entry(self, textvariable=self.image_x_var, validate='all', validatecommand=validator)

        image_y_label = ttk.Label(self, text='Image Y:', anchor=tk.W)
        image_y_entry = ttk.Entry(self, textvariable=self.image_y_var, validate='all', validatecommand=validator)

        quant_label = ttk.Label(self, text='Quantization:', anchor=tk.W)
        self.quant_select = ttk.Combobox(self, textvariable=self.quant_var, values=list(quantization_methods))

        dither_checkbox = ttk.Checkbutton(self, text='Dithering', variable=self.dither_var)

        self.image_view = ImageView(self, self.output_tim.to_image())
        # FIXME: hack
        self.image_view.transparency_var.trace_add('write', self.update_quantization)

        ok_button = ttk.Button(self, text='OK', command=self.on_ok)
        cancel_button = ttk.Button(self, text='Cancel', command=self.on_cancel)

        bpp_label.grid(row=0, column=0)
        bpp_select.grid(row=0, column=1)
        clut_x_label.grid(row=1, column=0)
        clut_x_entry.grid(row=1, column=1)
        clut_y_label.grid(row=2, column=0)
        clut_y_entry.grid(row=2, column=1)
        image_x_label.grid(row=3, column=0)
        image_x_entry.grid(row=3, column=1)
        image_y_label.grid(row=4, column=0)
        image_y_entry.grid(row=4, column=1)
        quant_label.grid(row=5, column=0)
        self.quant_select.grid(row=5, column=1)
        dither_checkbox.grid(row=6, column=0, columnspan=2)
        ok_button.grid(row=7, column=0, sticky=tk.SW)
        cancel_button.grid(row=7, column=2, sticky=tk.SE)
        self.image_view.grid(row=0, column=2, rowspan=7)

        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(7, weight=1)

        self.wait_visibility()
        self.grab_set()
        self.wait_window(self)

    @property
    def quantization_methods(self) -> dict[str, Image.Quantize]:
        methods = {}
        if self.input_image.mode != 'RGBA' or not self.image_view.with_transparency:
            methods['Median cut'] = Image.Quantize.MEDIANCUT
            methods['Maximum coverage'] = Image.Quantize.MAXCOVERAGE
        methods['Fast octree'] = Image.Quantize.FASTOCTREE
        if PIL.features.check_feature('libimagequant'):
            methods['libimagequant'] = Image.Quantize.LIBIMAGEQUANT
        return methods

    def on_ok(self, *_):
        self.output_tim = self.to_tim()
        self.destroy()

    def on_cancel(self, *_):
        self.output_tim = None
        self.destroy()

    def update_quantization(self, *_):
        if self.input_image.mode != 'RGBA':
            # only RGBA images have anything to update
            return

        quantization_methods = self.quantization_methods
        default_method = 'Median cut' if 'Median cut' in quantization_methods else 'Fast octree'
        if self.quant_var.get() not in quantization_methods:
            self.quant_var.set(default_method)
        self.quant_select.configure(values=list(quantization_methods))

    def to_tim(self) -> Tim:
        bpp = BitsPerPixel.from_bpp(int(self.bpp_var.get()))
        clut_x = int(self.clut_x_var.get() or '0')
        clut_y = int(self.clut_y_var.get() or '0')
        image_x = int(self.image_x_var.get() or '0')
        image_y = int(self.image_y_var.get() or '0')
        quantization_method = self.quantization_methods.get(self.quant_var.get())
        dither = Image.Dither.FLOYDSTEINBERG if self.dither_var.get() else Image.Dither.NONE

        image = self.input_image
        if image.mode == 'RGBA' and not self.image_view.with_transparency:
            image = image.convert('RGB')
        tim = Tim.from_image(image, bpp, quantization_method, dither)
        tim.clut_x = clut_x
        tim.clut_y = clut_y
        tim.image_x = image_x
        tim.image_y = image_y
        return tim

    def update_image(self, *_):
        self.image_view.image = self.output_tim = self.to_tim()
