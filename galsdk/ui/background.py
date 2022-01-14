import tkinter as tk
from tkinter import ttk
from typing import Optional

from PIL import ImageTk

from galsdk.ui.tab import Tab
from galsdk.project import Project, Stage
from galsdk.tim import TimDb
from psx.tim import Tim


class BackgroundTab(Tab):
    """Editor tab for viewing room background images"""

    dbs: list[tuple[str, Optional[TimDb]]]
    current_image: Optional[Tim]

    def __init__(self, project: Project):
        super().__init__('Background', project)

        self.tree = ttk.Treeview(self, selectmode='browse', show='tree')
        self.dbs = []
        self.current_image = None

        for stage in Stage:
            stage: Stage
            self.tree.insert('', tk.END, text=f'Stage {stage}', iid=stage, open=False)

            bg_manifest = self.project.get_stage_backgrounds(stage)
            for bg_db in bg_manifest:
                db_id = len(self.dbs)
                self.dbs.append((str(bg_db.path), None))
                bg_id = f'db_{db_id}'
                self.tree.insert(stage, tk.END, text=bg_db.name, iid=bg_id, open=False)
                # dummy item so we have the option to expand
                self.tree.insert(bg_id, tk.END, text='Dummy')

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
        image_options.grid(row=1, column=2, sticky=tk.S+tk.EW)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(2, weight=1)

        self.tree.bind('<<TreeviewSelect>>', self.show_image)
        self.tree.bind('<<TreeviewOpen>>', self.open_db)
        self.clut_select.bind('<<ComboboxSelected>>', self.update_image)

    def open_db(self, *_):
        focused = self.tree.focus()
        if focused.startswith('db_'):
            index = int(focused[3:])
            db_path = self.dbs[index]
            if db_path[1] is None:
                db = TimDb()
                db.read(db_path[0])
                self.dbs[index] = (db_path[0], db)
                db_id = f'db_{index}'
                self.tree.set_children(db_id)  # remove the dummy entry
                for i in range(len(db)):
                    self.tree.insert(db_id, tk.END, text=str(i), iid=f'img_{index}_{i}')

    def show_image(self, *_):
        selected = self.tree.selection()[0]
        if selected.startswith('img_'):
            db_index, img_index = [int(piece) for piece in selected[4:].split('_')]
            db = self.dbs[db_index][1]
            self.current_image = db[img_index]
            if self.current_image.num_palettes == 0:
                self.clut_select['state'] = 'disabled'
            else:
                self.clut_select['state'] = 'readonly'
                self.clut_select['values'] = [str(i) for i in range(self.current_image.num_palettes)]
            self.clut_var.set('0')
            self.update_image()

    def update_image(self, *_):
        if self.current_image is not None:
            clut_index = int(self.clut_var.get())
            with_transparency = self.transparency_var.get()
            zoom = self.zoom.get()
            image = self.current_image.to_image(clut_index, with_transparency)
            if abs(zoom - 1) > 0.01:
                image = image.resize((int(self.current_image.width*zoom), int(self.current_image.height*zoom)))
            tk_image = ImageTk.PhotoImage(image)
            self.image_label.configure(image=tk_image)
            self.image_label.image = tk_image
