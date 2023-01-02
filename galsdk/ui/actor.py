import tkinter as tk

from direct.showbase.ShowBase import ShowBase

from galsdk.ui.model_viewer import ModelViewerTab
from galsdk.project import Project


class ActorTab(ModelViewerTab):
    """Tab for viewing actor models"""

    def __init__(self, project: Project, base: ShowBase):
        super().__init__('Actor', project, base)

    def fill_tree(self):
        for model in self.project.get_actor_models():
            model_id = len(self.models)
            self.models.append(model)
            self.tree.insert('', tk.END, text=f'#{model.id}: {model.name}', iid=str(model_id))
