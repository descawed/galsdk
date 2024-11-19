import tkinter as tk

from direct.showbase.ShowBase import ShowBase

from galsdk.model import Segment
from galsdk.project import Project
from galsdk.ui.model_viewer import ModelViewerTab


class ModelTab(ModelViewerTab):
    """Tab for viewing arbitrary 3D models from the game"""

    def __init__(self, project: Project, base: ShowBase):
        super().__init__('Model', project, base)
        self.focus: tuple[int | None, int | None] = (None, None)

    def fill_tree(self):
        self.tree.insert('', tk.END, text='Actors', iid='actors', open=False)
        self.tree.insert('', tk.END, text='Items', iid='items', open=False)
        self.tree.insert('', tk.END, text='Other', iid='other', open=False)

        for category, models in zip(['actors', 'items', 'other'], self.project.get_all_models()):
            for i, model in models.items():
                model_id = len(self.models)
                self.models.append(model)
                iid = str(model_id)
                self.tree.insert(category, tk.END, text=f'#{i}: {model.name}', iid=iid)
                for segment in model.root_segments:
                    self.add_segment(iid, model_id, segment)

    def add_segment(self, parent_iid: str, model_id: int, segment: Segment):
        segment_iid = f'{model_id}_segment_{segment.index}'
        self.tree.insert(parent_iid, tk.END, text=f'#{segment.index}', iid=segment_iid)
        for child in segment.children:
            self.add_segment(segment_iid, model_id, child)

    def clear_focus(self):
        model_id = self.focus[0]
        if model_id is not None:
            self.models[model_id].unfocus()
            self.focus = (None, None)

    def select_model(self, _):
        super().select_model(_)

        iid = self.tree.selection()[0]
        if 'segment' not in iid:
            self.clear_focus()
            return

        pieces = iid.split('_')
        model_id = int(pieces[0])
        segment_index = int(pieces[2])

        self.set_model(model_id)
        if self.focus == (model_id, segment_index):
            return

        self.clear_focus()

        model = self.models[model_id]
        model.focus_segment(segment_index)
        self.focus = (model_id, segment_index)

    def set_active(self, is_active: bool):
        super().set_active(is_active)

        model_id, segment_index = self.focus
        if model_id is None:
            return

        model = self.models[model_id]
        if is_active:
            model.focus_segment(segment_index)
        else:
            model.unfocus()
