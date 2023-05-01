import tkinter as tk
import tkinter.filedialog as tkfile
from abc import ABCMeta, abstractmethod
from pathlib import Path
from tkinter import ttk

from direct.showbase.ShowBase import ShowBase

from galsdk.animation import Animation, AnimationDb
from galsdk.model import Model
from galsdk.project import Project
from galsdk.ui.animation import ActiveAnimation
from galsdk.ui.tab import Tab
from galsdk.ui.viewport import Viewport


class ModelViewer(Viewport):
    def __init__(self, name: str, base: ShowBase, width: int, height: int, *args, **kwargs):
        super().__init__(name, base, width, height, *args, **kwargs)

        self.camera_target = self.render_target.attachNewNode(f'{name}_camera_target')
        self.node_path = None
        self.active_animation = None

    def start_animation(self, animation: Animation):
        self.stop_animation()
        self.active_animation = ActiveAnimation(self.base, f'{self.name}_animation', self.node_path, animation)
        self.active_animation.play()

    def stop_animation(self):
        if self.active_animation:
            self.active_animation.remove()
            self.active_animation = None

    def set_model(self, model: Model | None):
        if self.node_path is not None:
            self.node_path.detachNode()
            self.node_path = None
        if model is not None:
            self.node_path = model.get_panda3d_model()
            panda_texture = model.get_panda3d_texture()
            self.node_path.setTexture(panda_texture, 1)
            self.node_path.setHpr(0, 0, 0)
            self.node_path.reparentTo(self.camera_target)
            self.set_target(self.camera_target)
        else:
            self.clear_target()


class ModelViewerTab(Tab, metaclass=ABCMeta):
    """Tab for viewing arbitrary 3D models from the game"""

    def __init__(self, name: str, project: Project, base: ShowBase):
        super().__init__(name, project)
        self.base = base
        self.models = []
        self.current_index = None
        self.exportable_ids = set()
        self.export_index = None

        self.tree = ttk.Treeview(self, selectmode='browse', show='tree')
        scroll = ttk.Scrollbar(self, command=self.tree.yview, orient='vertical')
        self.tree.configure(yscrollcommand=scroll.set)

        self.export_menu = tk.Menu(self, tearoff=False)
        self.export_menu.add_command(label='Export', command=self.on_export)

        self.model_frame = ModelViewer(name.lower(), self.base, 1280, 720, self)
        self.fill_tree()

        self.animations = self.project.get_animations()
        self.animation_set = None
        self.active_animation = None

        anim_frame = ttk.Frame(self)
        self.anim_set_var = tk.StringVar(self, 'None')
        self.anim_set_var.trace_add('write', self.on_change_anim_set)
        anim_set_label = ttk.Label(anim_frame, text='Animation set')
        options = ['None']
        options.extend(mf.name for mf in self.animations)
        self.anim_set_select = ttk.Combobox(anim_frame, textvariable=self.anim_set_var, values=options,
                                            state=tk.DISABLED)

        self.anim_var = tk.StringVar(self, 'None')
        self.anim_var.trace_add('write', self.on_change_anim)
        anim_label = ttk.Label(anim_frame, text='Animation')
        self.anim_select = ttk.Combobox(anim_frame, textvariable=self.anim_var, values=['None'], state=tk.DISABLED)

        self.tree.grid(row=0, column=0, rowspan=2, sticky=tk.NS + tk.W)
        scroll.grid(row=0, column=1, rowspan=2, sticky=tk.NS)
        self.model_frame.grid(row=0, column=2, sticky=tk.NE)
        anim_frame.grid(row=1, column=2, sticky=tk.S + tk.EW)
        anim_set_label.pack(padx=10, side=tk.LEFT)
        self.anim_set_select.pack(padx=10, side=tk.LEFT)
        anim_label.pack(padx=10, side=tk.LEFT)
        self.anim_select.pack(padx=10, side=tk.LEFT)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(2, weight=1)

        self.tree.bind('<<TreeviewSelect>>', self.select_model)
        self.tree.bind('<Button-3>', self.handle_right_click)

    @abstractmethod
    def fill_tree(self):
        pass

    def set_anim_set_index(self, index: int):
        mf = self.animations[index]
        self.anim_set_var.set(mf.name)

    def on_change_anim_set(self, *_):
        anim_set = self.anim_set_var.get()
        self.anim_var.set('None')
        if anim_set != 'None':
            mf = self.animations[anim_set]
            with mf.path.open('rb') as f:
                self.animation_set = AnimationDb.read(f)
            values = ['None']
            values.extend(str(i) for i, animation in enumerate(self.animation_set) if animation)
            self.anim_select.configure(values=values, state=tk.NORMAL)
        else:
            self.animation_set = None
            self.anim_select.configure(state=tk.DISABLED)

    def on_change_anim(self, *_):
        anim = self.anim_var.get()
        if anim != 'None':
            index = int(anim)
            self.model_frame.start_animation(self.animation_set[index])
        else:
            self.model_frame.stop_animation()

    def handle_right_click(self, event: tk.Event):
        try:
            index = int(self.tree.identify_row(event.y))
        except ValueError:
            return

        self.export_index = index
        self.export_menu.post(event.x_root, event.y_root)

    def on_export(self, *_):
        if self.export_index is None:
            return

        model = self.models[self.export_index]
        if filename := tkfile.asksaveasfilename(filetypes=[('3D models', '*.ply *.obj *.bam *.gltf'),
                                                           ('Images', '*.png *.jpg *.bmp *.tga *.webp *.tim'),
                                                           ('All Files', '*.*')]):
            path = Path(filename)
            model.export(path, path.suffix)

    def select_model(self, _):
        try:
            index = int(self.tree.selection()[0])
        except ValueError:
            # not a model
            return

        if index != self.current_index:
            self.current_index = index
            model = self.models[index]
            self.model_frame.set_model(model)
            self.anim_set_select.configure(state=tk.NORMAL)
            if model.anim_index is not None:
                self.set_anim_set_index(model.anim_index)
            else:
                self.anim_set_var.set('None')

    def set_active(self, is_active: bool):
        self.model_frame.set_active(is_active)
