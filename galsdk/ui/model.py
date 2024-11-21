import tkinter as tk
from tkinter import ttk

from direct.showbase.ShowBase import ShowBase

from galsdk.model import Segment
from galsdk.project import Project
from galsdk.ui.model_viewer import ModelViewerTab
from galsdk.ui.util import validate_int


class ModelTab(ModelViewerTab):
    """Tab for viewing arbitrary 3D models from the game"""

    def __init__(self, project: Project, base: ShowBase):
        self.manifest_models = []
        super().__init__('Model', project, base)
        self.focus: tuple[int | None, int | None] = (None, None)
        self.changed_model_indexes = set()
        self.changed_segments = set()

        self.int_validator = (self.register(validate_int), '%P')

        self.segment_index_var = tk.StringVar(self, 'N/A')
        self.segment_file_index_var = tk.StringVar(self, 'N/A')

        self.segment_trans_x_var = tk.StringVar(self)
        self.segment_trans_x_var.trace_add('write',
                                           lambda *_: self.change_segment_translation('x', self.segment_trans_x_var.get()))
        self.segment_trans_y_var = tk.StringVar(self)
        self.segment_trans_y_var.trace_add('write',
                                           lambda *_: self.change_segment_translation('y', self.segment_trans_y_var.get()))
        self.segment_trans_z_var = tk.StringVar(self)
        self.segment_trans_z_var.trace_add('write',
                                           lambda *_: self.change_segment_translation('z', self.segment_trans_z_var.get()))

        self.detail_frame = ttk.Frame(self)

        row_counter = 0
        index_label = ttk.Label(self.detail_frame, text='Index: ')
        index_value_label = ttk.Label(self.detail_frame, textvariable=self.segment_index_var)
        index_label.grid(row=row_counter, column=0, sticky=tk.W)
        index_value_label.grid(row=row_counter, column=1, sticky=tk.W)
        row_counter += 1

        file_index_label = ttk.Label(self.detail_frame, text='File Index: ')
        file_index_value_label = ttk.Label(self.detail_frame, textvariable=self.segment_file_index_var)
        file_index_label.grid(row=row_counter, column=0, sticky=tk.W)
        file_index_value_label.grid(row=row_counter, column=1, sticky=tk.W)
        row_counter += 1

        x_label = ttk.Label(self.detail_frame, text='Translation X: ')
        self.x_entry = ttk.Entry(self.detail_frame, textvariable=self.segment_trans_x_var, validate='all',
                                 validatecommand=self.int_validator)

        x_label.grid(row=row_counter, column=0)
        self.x_entry.grid(row=row_counter, column=1)
        row_counter += 1

        y_label = ttk.Label(self.detail_frame, text='Translation Y: ')
        self.y_entry = ttk.Entry(self.detail_frame, textvariable=self.segment_trans_y_var, validate='all',
                                 validatecommand=self.int_validator)

        y_label.grid(row=row_counter, column=0)
        self.y_entry.grid(row=row_counter, column=1)
        row_counter += 1

        z_label = ttk.Label(self.detail_frame, text='Translation Z: ')
        self.z_entry = ttk.Entry(self.detail_frame, textvariable=self.segment_trans_z_var, validate='all',
                                 validatecommand=self.int_validator)

        z_label.grid(row=row_counter, column=0)
        self.z_entry.grid(row=row_counter, column=1)

    def change_segment_translation(self, axis: str, str_value: str):
        kwargs = {axis: int(str_value)}
        model_id, segment_index = self.focus
        if self.models[model_id].set_segment_translation(segment_index, **kwargs) and self.focus not in self.changed_segments:
            if model_id not in self.changed_model_indexes:
                self.changed_model_indexes.add(model_id)
                model_iid = str(model_id)
                label = self.tree.item(model_iid, 'text')
                self.tree.item(model_iid, text=f'* {label}')

            self.changed_segments.add(self.focus)
            segment_iid = f'{model_id}_segment_{segment_index}'
            label = self.tree.item(segment_iid, 'text')
            self.tree.item(segment_iid, text=f'* {label}')

    def fill_tree(self):
        self.tree.insert('', tk.END, text='Actors', iid='actors', open=False)
        self.tree.insert('', tk.END, text='Items', iid='items', open=False)
        self.tree.insert('', tk.END, text='Other', iid='other', open=False)

        for category, models in zip(['actors', 'items', 'other'], self.project.get_all_models()):
            for i, manifest_model in models.items():
                model_id = len(self.models)
                self.manifest_models.append(manifest_model)
                model = manifest_model.obj
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

    def show_detail_widget(self):
        model_id, segment_index = self.focus
        model = self.models[model_id]
        segment = model.all_segments[segment_index]

        self.segment_index_var.set(str(segment.index))
        self.segment_file_index_var.set(str(segment.file_index))
        self.segment_trans_x_var.set(str(segment.offset[0]))
        self.segment_trans_y_var.set(str(segment.offset[1]))
        self.segment_trans_z_var.set(str(segment.offset[2]))

        if segment.can_change_translation:
            self.x_entry.config(state=tk.NORMAL)
            self.y_entry.config(state=tk.NORMAL)
            self.z_entry.config(state=tk.NORMAL)
        else:
            self.x_entry.config(state=tk.DISABLED)
            self.y_entry.config(state=tk.DISABLED)
            self.z_entry.config(state=tk.DISABLED)

        self.detail_frame.grid(row=0, column=2, rowspan=2)

    def clear_focus(self):
        model_id = self.focus[0]
        if model_id is not None:
            self.models[model_id].unfocus()
            self.focus = (None, None)
            self.detail_frame.grid_forget()

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
        self.show_detail_widget()

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

    def save(self):
        for model_id in self.changed_model_indexes:
            self.manifest_models[model_id].save()
            model_iid = str(model_id)
            label = self.tree.item(model_iid, 'text')
            if label.startswith('* '):
                self.tree.item(model_iid, text=label[2:])

        for model_id, segment_id in self.changed_segments:
            segment_iid = f'{model_id}_segment_{segment_id}'
            label = self.tree.item(segment_iid, 'text')
            if label.startswith('* '):
                self.tree.item(segment_iid, text=label[2:])

        self.changed_model_indexes.clear()
        self.changed_segments.clear()

    @property
    def has_unsaved_changes(self) -> bool:
        # TODO: implement saving
        return bool(self.changed_segments)
