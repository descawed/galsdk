import tkinter as tk
from functools import partial
from tkinter import ttk

from direct.showbase.ShowBase import ShowBase, Task

from galsdk.animation import Animation, AnimationDb, AnimationFlag
from galsdk.project import Project
from galsdk.ui.model_viewer import ModelViewer
from galsdk.ui.util import validate_int, validate_float
from galsdk.ui.tab import Tab


class AnimationTab(Tab):
    def __init__(self, project: Project, base: ShowBase):
        super().__init__('Animation', project)

        self.base = base
        self.manifest = self.project.get_animations()
        self.animation_dbs = []
        self.actors = {actor.name: actor for actor in self.project.get_actor_models() if actor is not None}
        self.selected_db_index = None
        self.selected_animation_index = None
        self.selected_element_index = None
        self.changed_dbs = set()
        self.context_menu_iid = None

        self.db_menu = tk.Menu(self, tearoff=False)
        self.copy_missing_menu = tk.Menu(self.db_menu, tearoff=False)
        self.copy_all_menu = tk.Menu(self.db_menu, tearoff=False)
        self.db_menu.add_cascade(label='Copy missing', menu=self.copy_missing_menu)
        self.db_menu.add_cascade(label='Copy all', menu=self.copy_all_menu)

        self.animation_menu = tk.Menu(self, tearoff=False)
        self.copy_animation_menu = tk.Menu(self.animation_menu, tearoff=False)
        self.animation_menu.add_cascade(label='Copy from', menu=self.copy_animation_menu)
        self.copy_animation_db_menus = []
        self.animation_menu.add_command(label='Delete', command=self.delete_animation)

        self.tree = ttk.Treeview(self, selectmode='browse', show='tree')
        scroll = ttk.Scrollbar(self, command=self.tree.yview, orient='vertical')
        self.tree.configure(yscrollcommand=scroll.set)

        self.int_validator = (self.register(validate_int), '%P')
        self.float_validator = (self.register(validate_float), '%P')

        self.ad_unknown1_var = tk.StringVar(self)
        self.ad_unknown1_var.trace_add('write',
                                       lambda *_: self.change_attack_data('unknown1', self.ad_unknown1_var.get()))
        self.ad_hit_angle_var = tk.StringVar(self)
        self.ad_hit_angle_var.trace_add('write', self.change_hit_angle)
        self.ad_unknown2_var = tk.StringVar(self)
        self.ad_unknown2_var.trace_add('write',
                                       lambda *_: self.change_attack_data('unknown2', self.ad_unknown2_var.get()))
        self.ad_damage_var = tk.StringVar(self)
        self.ad_damage_var.trace_add('write', lambda *_: self.change_attack_data('damage', self.ad_damage_var.get()))
        self.ad_type_var = tk.StringVar(self)
        self.ad_type_var.trace_add('write', lambda *_: self.change_attack_data('type', self.ad_type_var.get()))
        self.ad_unknown3_var = tk.StringVar(self)
        self.ad_unknown3_var.trace_add('write',
                                       lambda *_: self.change_attack_data('unknown3', self.ad_unknown3_var.get()))
        self.ad_unknown4_var = tk.StringVar(self)
        self.ad_unknown4_var.trace_add('write',
                                       lambda *_: self.change_attack_data('unknown4', self.ad_unknown4_var.get()))

        self.frame_flag_vars = {}
        for flag in AnimationFlag:
            var = tk.BooleanVar(self)
            self.frame_flag_vars[flag] = var
            var.trace_add('write', partial(self.change_frame_flag, flag))
        self.frame_trans_x_var = tk.StringVar(self)
        self.frame_trans_x_var.trace_add('write',
                                         lambda *_: self.change_frame_translation(0, self.frame_trans_x_var.get()))
        self.frame_trans_y_var = tk.StringVar(self)
        self.frame_trans_y_var.trace_add('write',
                                         lambda *_: self.change_frame_translation(1, self.frame_trans_y_var.get()))
        self.frame_trans_z_var = tk.StringVar(self)
        self.frame_trans_z_var.trace_add('write',
                                         lambda *_: self.change_frame_translation(2, self.frame_trans_z_var.get()))

        for i, mf in enumerate(self.manifest):
            with mf.path.open('rb') as f:
                db = AnimationDb.read(f, differential=not self.project.version.is_japanese_demo)

            self.animation_dbs.append(db)
            db_iid = str(i)
            self.tree.insert('', 'end', db_iid, text=f'#{i}: {mf.name}')
            for j, animation in enumerate(db):
                anim_iid = f'{db_iid}_{j}'
                self.tree.insert(db_iid, 'end', anim_iid, text=f'#{j}')
                self.add_animation_children(animation, anim_iid)

        self.viewport = ModelViewer('animation', base, 1280, 720, self)

        controls_frame = ttk.Frame(self)
        self.model_var = tk.StringVar(self, 'None')
        self.model_var.trace_add('write', self.update_model)
        model_label = ttk.Label(controls_frame, text='Model')
        self.model_select = ttk.Combobox(controls_frame, textvariable=self.model_var, state='readonly',
                                         values=['None', *self.actors])

        self.play_pause_text = tk.StringVar(value='\u25b6')
        self.play_pause = ttk.Button(controls_frame, textvariable=self.play_pause_text, command=self.play_pause)
        self.timeline_var = tk.IntVar(self)
        self.timeline = ttk.Scale(controls_frame, from_=0, to=1, variable=self.timeline_var,
                                  command=self.change_timeline)

        self.frame_counter_var = tk.StringVar(self, '0/0')
        self.frame_counter = ttk.Label(controls_frame, textvariable=self.frame_counter_var)

        model_label.pack(padx=10, side=tk.LEFT)
        self.model_select.pack(side=tk.LEFT)
        self.play_pause.pack(padx=10, side=tk.LEFT)
        self.timeline.pack(expand=1, anchor=tk.CENTER, fill=tk.BOTH, side=tk.LEFT)
        self.frame_counter.pack(padx=10, side=tk.RIGHT)

        self.tree.grid(row=0, column=0, rowspan=2, sticky=tk.NS + tk.W)
        scroll.grid(row=0, column=1, rowspan=2, sticky=tk.NS)
        self.viewport.grid(row=0, column=3, sticky=tk.NS + tk.E)
        controls_frame.grid(row=1, column=3, sticky=tk.EW + tk.S)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(3, weight=1)

        self.attack_data_detail = self.make_attack_data_detail()
        self.frame_detail = self.make_frame_detail()

        self.tree.bind('<<TreeviewSelect>>', self.select_item)
        self.tree.bind('<Button-3>', self.handle_right_click)
        self.bind('<Configure>', self.resize_3d)

        self.base.taskMgr.add(self.update_ui, 'animation_timer')

    def delete_animation(self, *_):
        pieces = self.context_menu_iid.split('_')
        db_index = int(pieces[0])
        anim_index = int(pieces[1])
        self.animation_dbs[db_index][anim_index] = None
        self.tree.delete(*self.tree.get_children(self.context_menu_iid))
        self.tree.item(self.context_menu_iid, text=f'* #{anim_index}')
        self.update_model()

    def add_animation_children(self, animation: Animation, iid: str):
        if animation is None:
            self.tree.delete(*self.tree.get_children(iid))
            return

        attack_data_iid = f'{iid}_attack'
        self.tree.insert(iid, 'end', attack_data_iid, text='Attack Data')
        for i in range(len(animation.attack_data)):
            self.tree.insert(attack_data_iid, 'end', f'{attack_data_iid}_{i}', text=f'* #{i}')

        frame_iid = f'{iid}_frame'
        self.tree.insert(iid, 'end', frame_iid, text='Frames')
        for i in range(len(animation.frames)):
            self.tree.insert(frame_iid, 'end', f'{frame_iid}_{i}', text=f'* #{i}')

    def change_db(self, index: int):
        self.changed_dbs.add(index)
        self.notify_change()
        db_iid = str(index)
        db_name = self.manifest[index].name
        self.tree.item(db_iid, text=f'* #{self.selected_db_index}: {db_name}')
        if self.selected_db_index == index:
            self.update_model()

    def copy_db_missing(self, from_index: int, *_):
        to_index = int(self.context_menu_iid)
        to_db = self.animation_dbs[to_index]
        any_added = False
        for i, animation in enumerate(self.animation_dbs[from_index]):
            iid = f'{to_index}_{i}'
            if i >= len(to_db):
                to_db.append(None)
                self.tree.insert(self.context_menu_iid, 'end', iid, text=f'* #{i}')
                any_added = True

            if to_db[i] is None and animation is not None:
                self.tree.item(iid, text=f'* #{i}')
                to_db[i] = animation
                self.add_animation_children(animation, iid)
                any_added = True

        if any_added:
            self.change_db(to_index)

    def copy_db_all(self, from_index: int, *_):
        to_index = int(self.context_menu_iid)
        to_db = self.animation_dbs[to_index]
        for i, animation in enumerate(self.animation_dbs[from_index]):
            iid = f'{to_index}_{i}'
            if i >= len(to_db):
                to_db.append(None)
                self.tree.insert(self.context_menu_iid, 'end', iid, text=f'* #{i}')
            else:
                self.tree.delete(*self.tree.get_children(self.context_menu_iid))

            to_db[i] = animation
            self.add_animation_children(animation, iid)

        self.change_db(to_index)

    def copy_animation(self, from_db_index: int, from_anim_index: int, *_):
        pieces = self.context_menu_iid.split('_')
        to_db_index = int(pieces[0])
        to_anim_index = int(pieces[1])
        animation = self.animation_dbs[from_db_index][from_anim_index]
        self.animation_dbs[to_db_index][to_anim_index] = animation
        self.add_animation_children(animation, self.context_menu_iid)
        self.tree.item(self.context_menu_iid, text=f'* #{to_anim_index}')
        mf = self.manifest[to_db_index]
        self.tree.item(str(to_db_index), text=f'* #{to_db_index}: {mf.name}')
        self.changed_dbs.add(to_db_index)
        self.notify_change()
        if self.selected_db_index == to_db_index and self.selected_animation_index == to_anim_index:
            self.update_model()

    def populate_db_menu(self):
        selected_db_index = int(self.context_menu_iid)
        self.copy_missing_menu.delete(0, 'end')
        self.copy_all_menu.delete(0, 'end')
        for i, mf in enumerate(self.manifest):
            if i == selected_db_index:
                continue

            self.copy_missing_menu.add_command(label=f'#{i}: {mf.name}', command=partial(self.copy_db_missing, i))
            self.copy_all_menu.add_command(label=f'#{i}: {mf.name}', command=partial(self.copy_db_all, i))

    def populate_animation_menu(self):
        pieces = self.context_menu_iid.split('_')
        db_index = int(pieces[0])
        anim_index = int(pieces[1])

        self.copy_animation_menu.delete(0, 'end')
        for menu in self.copy_animation_db_menus:
            menu.destroy()
        self.copy_animation_db_menus.clear()

        for i, mf in enumerate(self.manifest):
            db = self.animation_dbs[i]
            sub_menu = tk.Menu(self.copy_animation_menu, tearoff=False)
            for j, animation in enumerate(db):
                if i == db_index and j == anim_index:
                    continue
                sub_menu.add_command(label=f'#{j}', command=partial(self.copy_animation, i, j))
            self.copy_animation_menu.add_cascade(label=f'#{i}: {mf.name}', menu=sub_menu)
            self.copy_animation_db_menus.append(sub_menu)

    def handle_right_click(self, event: tk.Event):
        iid = self.tree.identify_row(event.y)
        if not iid:
            self.db_menu.unpost()
            self.animation_menu.unpost()
            return

        depth = iid.count('_')
        if depth > 1:
            self.db_menu.unpost()
            self.animation_menu.unpost()
            return

        self.context_menu_iid = iid
        if depth == 0:
            self.populate_db_menu()
            self.db_menu.post(event.x_root, event.y_root)
        else:
            self.populate_animation_menu()
            self.animation_menu.post(event.x_root, event.y_root)

    def mark_change(self, change_type: str):
        if (self.selected_db_index is None or self.selected_animation_index is None
                or self.selected_element_index is None):
            return

        self.changed_dbs.add(self.selected_db_index)
        iid = f'{self.selected_db_index}_{self.selected_animation_index}_{change_type}_{self.selected_element_index}'
        self.tree.item(iid, text=f'* #{self.selected_element_index}')

        anim_iid = f'{self.selected_db_index}_{self.selected_animation_index}'
        self.tree.item(anim_iid, text=f'* #{self.selected_animation_index}')

        db_iid = str(self.selected_db_index)
        db_name = self.manifest[self.selected_db_index].name
        self.tree.item(db_iid, text=f'* #{self.selected_db_index}: {db_name}')

        self.notify_change()

    def change_frame_flag(self, flag: AnimationFlag, *_):
        animation = self.animation_dbs[self.selected_db_index][self.selected_animation_index]
        frame = animation.frames[self.selected_element_index]
        if self.frame_flag_vars[flag].get():
            if not frame.flags & flag:
                frame.flags |= flag
                self.mark_change('frame')
        else:
            if frame.flags & flag:
                frame.flags &= ~flag
                self.mark_change('frame')

    def change_frame_translation(self, index: int, value: str):
        try:
            int_value = int(value)
        except ValueError:
            return

        animation = self.animation_dbs[self.selected_db_index][self.selected_animation_index]
        frame = animation.frames[self.selected_element_index]
        translation = list(frame.translation)
        if translation[index] != int_value:
            translation[index] = int_value
            frame.translation = tuple(translation)
            self.mark_change('frame')

    def change_attack_data(self, field: str, value: str):
        try:
            int_value = int(value)
        except ValueError:
            return

        animation = self.animation_dbs[self.selected_db_index][self.selected_animation_index]
        attack_data = animation.attack_data[self.selected_element_index]
        if getattr(attack_data, field) != int_value:
            setattr(attack_data, field, int_value)
            self.mark_change('attack')

    def change_hit_angle(self, *_):
        try:
            angle = float(self.ad_hit_angle_var.get())
        except ValueError:
            return

        animation = self.animation_dbs[self.selected_db_index][self.selected_animation_index]
        attack_data = animation.attack_data[self.selected_element_index]
        int_angle = int(4096 * angle / 360)
        if attack_data.hit_angle != int_angle:
            attack_data.hit_angle = int_angle
            self.mark_change('attack')

    def change_timeline(self, _):
        self.viewport.set_animation_frame(self.timeline_var.get())

    def play_pause(self):
        if self.viewport.is_playing:
            self.viewport.pause_animation()
        else:
            self.viewport.play_animation()

    def update_ui(self, _) -> int:
        frame_index, last_frame = self.viewport.animation_position
        self.frame_counter_var.set(f'{frame_index} / {last_frame}')
        if self.viewport.is_playing:
            self.timeline_var.set(frame_index)
            self.play_pause_text.set('\u23f8')
        else:
            self.play_pause_text.set('\u25b6')
        return Task.cont

    def update_model(self, *_):
        model = self.actors.get(self.model_var.get())
        if model is None:
            self.viewport.set_model(None)
            return

        self.viewport.set_model(model)

        if self.selected_animation_index is None:
            self.viewport.stop_animation()
            return

        animation = self.animation_dbs[self.selected_db_index][self.selected_animation_index]
        if animation is None:
            self.viewport.stop_animation()
        else:
            self.viewport.start_animation(animation)
            self.timeline.configure(to=self.viewport.animation_position[1])

    def select_item(self, _=None):
        self.db_menu.unpost()
        self.animation_menu.unpost()

        selection = self.tree.selection()
        if not selection:
            return

        self.selected_animation_index = None
        self.selected_element_index = None

        iid = selection[0]
        pieces = iid.split('_')
        old_db_index = self.selected_db_index
        old_animation_index = self.selected_animation_index
        self.selected_db_index = int(pieces[0])
        if old_db_index != self.selected_db_index:
            for name, actor in self.actors.items():
                if actor.anim_index == self.selected_db_index:
                    self.model_var.set(name)
                    break

        if len(pieces) > 1:
            self.selected_animation_index = int(pieces[1])
            if self.selected_db_index != old_db_index or self.selected_animation_index != old_animation_index:
                self.update_model()
        if len(pieces) > 3:
            self.selected_element_index = int(pieces[3])
            animation = self.animation_dbs[self.selected_db_index][self.selected_animation_index]
            if animation is None:
                self.frame_detail.grid_forget()
                self.attack_data_detail.grid_forget()
            elif pieces[2] == 'attack':
                self.frame_detail.grid_forget()
                self.attack_data_detail.grid(row=0, column=2, rowspan=2)

                attack_data = animation.attack_data[self.selected_element_index]
                self.ad_unknown1_var.set(str(attack_data.unknown1))
                self.ad_hit_angle_var.set(f'{360 * attack_data.hit_angle / 4096:.1f}')
                self.ad_unknown2_var.set(str(attack_data.unknown2))
                self.ad_damage_var.set(str(attack_data.damage))
                self.ad_type_var.set(str(attack_data.type))
                self.ad_unknown3_var.set(str(attack_data.unknown3))
                self.ad_unknown4_var.set(str(attack_data.unknown4))
            else:
                self.attack_data_detail.grid_forget()
                self.frame_detail.grid(row=0, column=2, rowspan=2)

                frame = animation.frames[self.selected_element_index]
                for flag in AnimationFlag:
                    self.frame_flag_vars[flag].set(bool(frame.flags & flag))
                self.frame_trans_x_var.set(str(frame.translation[0]))
                self.frame_trans_y_var.set(str(frame.translation[1]))
                self.frame_trans_z_var.set(str(frame.translation[2]))
        else:
            self.frame_detail.grid_forget()
            self.attack_data_detail.grid_forget()

    def resize_3d(self, _=None):
        self.update()
        x, y, width, height = self.grid_bbox(3, 0)
        self.viewport.resize(width, height)

    def set_active(self, is_active: bool):
        self.viewport.set_active(is_active)
        if is_active:
            self.resize_3d()

    def close(self):
        self.viewport.close()
        self.base.taskMgr.remove('animation_timer')

    def make_frame_detail(self) -> ttk.Frame:
        frame = ttk.Frame(self)

        row_counter = 0
        for flag in AnimationFlag:
            checkbox = ttk.Checkbutton(frame, text=flag.name, variable=self.frame_flag_vars[flag])
            checkbox.grid(row=row_counter, column=0, columnspan=2)
            row_counter += 1

        x_label = ttk.Label(frame, text='Translation X: ')
        x_entry = ttk.Entry(frame, textvariable=self.frame_trans_x_var, validate='all',
                            validatecommand=self.int_validator)

        x_label.grid(row=row_counter, column=0)
        x_entry.grid(row=row_counter, column=1)
        row_counter += 1

        y_label = ttk.Label(frame, text='Translation Y: ')
        y_entry = ttk.Entry(frame, textvariable=self.frame_trans_y_var, validate='all',
                            validatecommand=self.int_validator)

        y_label.grid(row=row_counter, column=0)
        y_entry.grid(row=row_counter, column=1)
        row_counter += 1

        z_label = ttk.Label(frame, text='Translation Z: ')
        z_entry = ttk.Entry(frame, textvariable=self.frame_trans_z_var, validate='all',
                            validatecommand=self.int_validator)

        z_label.grid(row=row_counter, column=0)
        z_entry.grid(row=row_counter, column=1)

        return frame

    def make_attack_data_detail(self) -> ttk.Frame:
        frame = ttk.Frame(self)

        unknown1_label = ttk.Label(frame, text='Unknown: ')
        unknown1_entry = ttk.Entry(frame, textvariable=self.ad_unknown1_var, validate='all',
                                   validatecommand=self.int_validator)

        hit_angle_label = ttk.Label(frame, text='Hit Angle: ')
        hit_angle_entry = ttk.Entry(frame, textvariable=self.ad_hit_angle_var, validate='all',
                                    validatecommand=self.float_validator)

        unknown2_label = ttk.Label(frame, text='Unknown: ')
        unknown2_entry = ttk.Entry(frame, textvariable=self.ad_unknown2_var, validate='all',
                                   validatecommand=self.int_validator)

        damage_label = ttk.Label(frame, text='Damage: ')
        damage_entry = ttk.Entry(frame, textvariable=self.ad_damage_var, validate='all',
                                 validatecommand=self.int_validator)

        type_label = ttk.Label(frame, text='Type: ')
        type_entry = ttk.Entry(frame, textvariable=self.ad_type_var, validate='all', validatecommand=self.int_validator)

        unknown3_label = ttk.Label(frame, text='Unknown: ')
        unknown3_entry = ttk.Entry(frame, textvariable=self.ad_unknown3_var, validate='all',
                                   validatecommand=self.int_validator)

        unknown4_label = ttk.Label(frame, text='Unknown: ')
        unknown4_entry = ttk.Entry(frame, textvariable=self.ad_unknown4_var, validate='all',
                                   validatecommand=self.int_validator)

        unknown1_label.grid(row=0, column=0)
        unknown1_entry.grid(row=0, column=1)
        hit_angle_label.grid(row=1, column=0)
        hit_angle_entry.grid(row=1, column=1)
        unknown2_label.grid(row=2, column=0)
        unknown2_entry.grid(row=2, column=1)
        damage_label.grid(row=3, column=0)
        damage_entry.grid(row=3, column=1)
        type_label.grid(row=4, column=0)
        type_entry.grid(row=4, column=1)
        unknown3_label.grid(row=5, column=0)
        unknown3_entry.grid(row=5, column=1)
        unknown4_label.grid(row=6, column=0)
        unknown4_entry.grid(row=6, column=1)

        return frame

    def clear_change_markers(self, iid: str = None):
        for child in self.tree.get_children(iid):
            name = self.tree.item(child, 'text')
            if name.startswith('* '):
                self.tree.item(child, text=name[2:])
            self.clear_change_markers(child)

    def save(self):
        for db_index in self.changed_dbs:
            db = self.animation_dbs[db_index]
            mf = self.manifest[db_index]
            with mf.path.open('wb') as f:
                db.write(f)

        self.changed_dbs.clear()
        self.clear_change_markers()

    @property
    def has_unsaved_changes(self) -> bool:
        return len(self.changed_dbs) > 0
