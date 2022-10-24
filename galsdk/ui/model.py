import tkinter as tk

from direct.showbase.ShowBase import ShowBase

from galsdk.ui.model_viewer import ModelViewerTab
from galsdk.project import Project


class ModelTab(ModelViewerTab):
    """Tab for viewing arbitrary 3D models from the game"""

    def __init__(self, project: Project, base: ShowBase):
        super().__init__('Model', project, base)

    def fill_tree(self):
        self.tree.insert('', tk.END, text='Actors', iid='actors', open=False)
        self.tree.insert('', tk.END, text='Items', iid='items', open=False)
        self.tree.insert('', tk.END, text='Other', iid='other', open=False)

        for category, models in zip(['actors', 'items', 'other'], self.project.get_all_models()):
            for i, model in models.items():
                model_id = len(self.models)
                self.models.append(model)
                self.tree.insert(category, tk.END, text=f'#{i}: {model.name}', iid=str(model_id))
