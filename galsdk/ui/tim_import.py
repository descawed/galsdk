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
        self.image_view = None
        quantization_methods = self.quantization_methods
        default_method = 'Median cut' if 'Median cut' in quantization_methods else 'Fast octree'

        validator = (self.register(validate_int), '%P')

        self.bpp_var = tk.StringVar(self, '8')
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
        self.clut_x_var.trace_add('write', self.update_labels)
        self.clut_y_var.trace_add('write', self.update_labels)
        self.image_x_var.trace_add('write', self.update_labels)
        self.image_y_var.trace_add('write', self.update_labels)

        self.output_tim = self.to_tim()

        option_frame = ttk.Frame(self)
        bpp_label = ttk.Label(option_frame, text='BPP:', anchor=tk.W)
        bpp_select = ttk.Combobox(option_frame, textvariable=self.bpp_var, values=['4', '8', '16', '24'],
                                  state='readonly')

        clut_x_label = ttk.Label(option_frame, text='CLUT X:', anchor=tk.W)
        clut_x_entry = ttk.Entry(option_frame, textvariable=self.clut_x_var, validate='all', validatecommand=validator)

        clut_y_label = ttk.Label(option_frame, text='CLUT Y:', anchor=tk.W)
        clut_y_entry = ttk.Entry(option_frame, textvariable=self.clut_y_var, validate='all', validatecommand=validator)

        image_x_label = ttk.Label(option_frame, text='Image X:', anchor=tk.W)
        image_x_entry = ttk.Entry(option_frame, textvariable=self.image_x_var, validate='all',
                                  validatecommand=validator)

        image_y_label = ttk.Label(option_frame, text='Image Y:', anchor=tk.W)
        image_y_entry = ttk.Entry(option_frame, textvariable=self.image_y_var, validate='all',
                                  validatecommand=validator)

        quant_label = ttk.Label(option_frame, text='Quantization:', anchor=tk.W)
        self.quant_select = ttk.Combobox(option_frame, textvariable=self.quant_var, values=list(quantization_methods),
                                         state='readonly')

        self.dither_checkbox = ttk.Checkbutton(option_frame, text='Dithering', variable=self.dither_var)

        bpp_label.grid(row=0, column=0, pady=5, padx=5)
        bpp_select.grid(row=0, column=1, pady=5, padx=5)
        clut_x_label.grid(row=1, column=0, pady=5, padx=5)
        clut_x_entry.grid(row=1, column=1, pady=5, padx=5)
        clut_y_label.grid(row=2, column=0, pady=5, padx=5)
        clut_y_entry.grid(row=2, column=1, pady=5, padx=5)
        image_x_label.grid(row=3, column=0, pady=5, padx=5)
        image_x_entry.grid(row=3, column=1, pady=5, padx=5)
        image_y_label.grid(row=4, column=0, pady=5, padx=5)
        image_y_entry.grid(row=4, column=1, pady=5, padx=5)
        quant_label.grid(row=5, column=0, pady=5, padx=5)
        self.quant_select.grid(row=5, column=1, pady=5, padx=5)
        self.dither_checkbox.grid(row=6, column=0, columnspan=2, sticky=tk.N, padx=5, pady=5)

        self.image_view = ImageView(self, self.output_tim)
        # FIXME: hack
        self.image_view.transparency_var.trace_add('write', self.update_quantization)

        ok_button = ttk.Button(self, text='OK', command=self.on_ok)
        cancel_button = ttk.Button(self, text='Cancel', command=self.on_cancel)
        self.protocol('WM_DELETE_WINDOW', self.on_cancel)

        option_frame.grid(row=0, column=0, sticky=tk.EW)
        self.image_view.grid(row=0, column=1, sticky=tk.NSEW, padx=5, pady=5)
        ok_button.grid(row=1, column=0, sticky=tk.SW, padx=5, pady=5)
        cancel_button.grid(row=1, column=1, sticky=tk.SE, padx=5, pady=5)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.wait_visibility()
        self.grab_set()
        self.wait_window(self)

    @property
    def quantization_methods(self) -> dict[str, Image.Quantize]:
        methods = {}
        if self.input_image.mode != 'RGBA' or not self.with_transparency:
            methods['Median cut'] = Image.Quantize.MEDIANCUT
            methods['Maximum coverage'] = Image.Quantize.MAXCOVERAGE
        methods['Fast octree'] = Image.Quantize.FASTOCTREE
        if PIL.features.check_feature('libimagequant'):
            methods['libimagequant'] = Image.Quantize.LIBIMAGEQUANT
        return methods

    @property
    def with_transparency(self) -> bool:
        if self.image_view is not None:
            return self.image_view.with_transparency
        return self.input_image.has_transparency_data

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
        if image.mode == 'RGBA' and not self.with_transparency:
            image = image.convert('RGB')
        tim = Tim.from_image(image, bpp, quantization_method, dither)
        tim.clut_x = clut_x
        tim.clut_y = clut_y
        tim.image_x = image_x
        tim.image_y = image_y
        return tim

    def update_labels(self, *_):
        self.output_tim.clut_x = self.clut_x_var.get()
        self.output_tim.clut_y = self.clut_y_var.get()
        self.output_tim.image_x = self.image_x_var.get()
        self.output_tim.image_y = self.image_y_var.get()
        self.image_view.update_labels()

    def update_image(self, *_):
        if self.bpp_var.get() in ['4', '8']:
            self.quant_select.configure(state='readonly')
            self.dither_checkbox.configure(state=tk.NORMAL)
        else:
            self.quant_select.configure(state=tk.DISABLED)
            self.dither_checkbox.configure(state=tk.DISABLED)
        self.image_view.image = self.output_tim = self.to_tim()
