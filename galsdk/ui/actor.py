import tkinter as tk
from tkinter import ttk

from direct.showbase.ShowBase import ShowBase

from galsdk.ui.model import ModelViewer
from galsdk.ui.tab import Tab
from galsdk.project import Project


class ActorTab(Tab):
    """Tab for viewing actor models"""

    def __init__(self, project: Project, base: ShowBase):
        super().__init__('Actors', project)
        self.base = base
        self.models = []
        self.current_index = None

        self.tree = ttk.Treeview(self, selectmode='browse', show='tree')
        scroll = ttk.Scrollbar(self, command=self.tree.yview, orient='vertical')
        self.tree.configure(yscrollcommand=scroll.set)

        for model in self.project.get_actor_models():
            model_id = len(self.models)
            self.models.append(model)
            self.tree.insert('', tk.END, text=model.name, iid=str(model_id))

        self.model_frame = ModelViewer('actor', self.base, 1280, 720, self)

        self.tree.grid(row=0, column=0, sticky=tk.NS + tk.W)
        scroll.grid(row=0, column=1, sticky=tk.NS)
        self.model_frame.grid(row=0, column=2, sticky=tk.NS + tk.E)

        self.grid_columnconfigure(2, weight=1)

        self.tree.bind('<<TreeviewSelect>>', self.select_model)

    def select_model(self, _):
        try:
            index = int(self.tree.selection()[0])
        except ValueError:
            # not a model
            return

        if index != self.current_index:
            self.current_index = index
            self.model_frame.set_model(self.models[index])
