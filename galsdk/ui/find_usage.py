import tkinter as tk
from tkinter import ttk

from galsdk.game import ArgumentType, Stage, KNOWN_FUNCTIONS
from galsdk.project import Project
from galsdk.ui.util import get_preview_string


class FindUsageDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk, project: Project):
        super().__init__(parent)
        self.transient(parent)
        self.project = project

        self.title('Find Usages')

        self.type_var = tk.StringVar(self, 'Message')
        self.type_var.trace_add('write', self.on_change_type)
        self.object_var = tk.StringVar(self)
        self.unused_var = tk.BooleanVar(self)
        self.unused_var.trace_add('write', self.on_toggle_unused)

        type_label = ttk.Label(self, text='Type:', anchor=tk.W)
        type_select = ttk.Combobox(self, textvariable=self.type_var, state='readonly',
                                   values=['Message', 'Item TIM', 'Item', 'Background', 'Actor', 'Function', 'Flag',
                                           'Empty Trigger'])

        self.unused_checkbox = ttk.Checkbutton(self, text='Find unused', variable=self.unused_var)

        object_label = ttk.Label(self, text='Object:', anchor=tk.W)
        self.object_select = ttk.Combobox(self, textvariable=self.object_var, state='readonly')

        result_frame = ttk.Labelframe(self, text='Results')
        self.result_text = tk.Text(result_frame, width=50, height=30, state=tk.DISABLED)
        result_scroll = ttk.Scrollbar(result_frame, command=self.result_text.yview)
        self.result_text.configure(yscrollcommand=result_scroll.set)

        self.result_text.grid(row=0, column=0, sticky=tk.NSEW)
        result_scroll.grid(row=0, column=1, sticky=tk.NSEW)
        result_frame.grid_rowconfigure(0, weight=1)
        result_frame.grid_columnconfigure(0, weight=1)

        search_button = ttk.Button(self, text='Search', command=self.search)

        type_label.grid(row=0, column=0, padx=5, pady=5)
        type_select.grid(row=0, column=1, padx=5, pady=5)
        self.unused_checkbox.grid(row=1, column=0, columnspan=2, padx=5, pady=5)
        object_label.grid(row=2, column=0, padx=5, pady=5)
        self.object_select.grid(row=2, column=1, padx=5, pady=5)
        result_frame.grid(row=3, column=0, columnspan=2, padx=5, pady=5)
        search_button.grid(row=4, column=0, padx=5, pady=5)

        self.grid_columnconfigure(1, weight=1)

        self.on_change_type()

    def on_toggle_unused(self, *_):
        state = tk.DISABLED if self.unused_var.get() or self.type_var.get() == 'Empty Trigger' else 'readonly'
        self.object_select.configure(state=state)

    def get_all_objects(self, preview_len: int = 20) -> dict[tuple[Stage | None, int | str], str]:
        out = {}
        match self.type_var.get():
            case 'Message':
                for stage in Stage:
                    stage: Stage
                    string_db = self.project.get_stage_strings(stage)
                    for string_id, string in string_db.obj.iter_ids():
                        out[(stage, string_id)] = get_preview_string(f'{stage} {string_id}: {string}', preview_len)
            case 'Item TIM':
                for art_manifest in self.project.get_art_manifests():
                    if art_manifest.name == 'ITEMTIM':
                        for i, mf in enumerate(art_manifest):
                            out[(None, i)] = f'{i}: {mf.name}'
                        break
            case 'Item':
                for i, name in enumerate(self.project.version.key_item_names):
                    out[(None, i)] = f'{i}: {name}'
            case 'Background':
                for stage in Stage:
                    stage: Stage
                    for i, mf in enumerate(self.project.get_stage_backgrounds(stage)):
                        out[(stage, i)] = f'{stage} {i}: {mf.name}'
            case 'Actor':
                for actor in self.project.get_actor_models(True):
                    out[(None, actor.id)] = f'{actor.id}: {actor.name}'
            case 'Function':
                addresses = self.project.version.addresses
                for name, function in KNOWN_FUNCTIONS.items():
                    if name in addresses or function.can_be_pseudo:
                        out[(None, name)] = name
            case 'Flag':
                for stage, num_flags in zip(Stage, self.project.version.flag_counts):
                    for flag in range(num_flags):
                        out[(stage, flag)] = f'{stage} {flag}'
            case _:
                out[(None, 'N/A')] = 'N/A'

        return out

    def on_change_type(self, *_):
        values = list(self.get_all_objects().values())
        self.object_var.set(values[0])
        self.object_select.configure(values=values)
        self.on_toggle_unused()
        self.unused_checkbox.configure(state=tk.DISABLED if self.type_var.get() == 'Empty Trigger' else tk.NORMAL)

    @property
    def argument_type(self) -> ArgumentType | None:
        match self.type_var.get():
            case 'Message':
                return ArgumentType.MESSAGE
            case 'Item TIM':
                return ArgumentType.ITEMTIM
            case 'Item':
                return ArgumentType.KEY_ITEM
            case 'Flag':
                return ArgumentType.FLAG
            case _:
                return None

    def get_selection(self) -> tuple[Stage | None, int | str | None]:
        if self.unused_var.get() and self.type_var.get() != 'Empty Trigger':
            return None, None

        object_selection = self.object_var.get()
        if ':' not in object_selection and ' ' not in object_selection:
            return None, object_selection

        id_str = object_selection.split(':')[0]
        if ' ' in id_str:
            stage, id_value = id_str.split()
            return Stage(stage), int(id_value)
        return None, int(id_str)

    def search(self, *_):
        stage, id_value = self.get_selection()
        if stage is None:
            stages = list(Stage)
        else:
            stages = [stage]

        modules = []
        for each in stages:
            each: Stage
            modules.extend(module.obj for module in self.project.get_stage_rooms(each))

        object_type = self.type_var.get()
        expected_arg_type = self.argument_type
        usages = set()
        ids_seen = set()
        for module in modules:
            module_stage = Stage(module.name[0])
            include_stage = object_type in ['Background', 'Message', 'Flag']
            match object_type:
                case 'Item':
                    for i, trigger in enumerate(module.triggers.triggers):
                        if trigger.type.has_item:
                            ids_seen.add((None, trigger.item_id))
                            if trigger.item_id == id_value:
                                usages.add(f'{module.name}: trigger {i} ({trigger.description})')
                case 'Background':
                    for i, background_set in enumerate(module.backgrounds):
                        for j, background in enumerate(background_set.backgrounds):
                            ids_seen.add((module_stage, background.index))
                            if background.index == id_value:
                                usages.add(f'{module.name}: background set {i} background {j}')
                case 'Actor':
                    for i, actor_layout_set in enumerate(module.actor_layouts):
                        for j, actor_layout in enumerate(actor_layout_set.layouts):
                            for k, actor in enumerate(actor_layout.actors):
                                ids_seen.add((None, actor.type))
                                if actor.type == id_value:
                                    usages.add(f'{module.name}: actor layout set {i} layout {j} instance {k}')
                case 'Empty Trigger':
                    for i, trigger in enumerate(module.triggers.triggers):
                        callbacks = [('enabled', trigger.enabled_callback), ('action', trigger.trigger_callback)]
                        for name, callback in callbacks:
                            if callback in module.functions and not module.functions[callback].calls:
                                usages.add(f'{module.name}: trigger {i} ({trigger.description}) {name} callback')

            if expected_arg_type is not None or object_type == 'Function':
                for address, function in module.functions.items():
                    for call in function.calls:
                        if object_type == 'Function':
                            ids_seen.add((None, call.name))
                            if call.name == id_value:
                                usages.add(f'{module.name}: function {address:08X} @ {call.call_address:08X}')
                            continue

                        arg_stage = None
                        arg_id = None
                        for argument, arg_type in zip(call.arguments, KNOWN_FUNCTIONS[call.name].arguments):
                            if argument.value is None:
                                continue

                            if arg_type == ArgumentType.STAGE:
                                arg_stage = Stage.from_int(argument.value)
                            elif arg_type == expected_arg_type:
                                arg_id = argument.value
                                if expected_arg_type == ArgumentType.MESSAGE:
                                    arg_id &= 0x3fff

                        if arg_id is not None:
                            id_stage = arg_stage if arg_stage is not None else module_stage
                            ids_seen.add((id_stage if include_stage else None, arg_id))
                            if arg_id == id_value:
                                usages.add(
                                    f'{module.name}: function {address:08X} {call.name} @ {call.call_address:08X}'
                                )

        if id_value is None:
            # we're searching for unused IDs
            all_objects = self.get_all_objects(30)
            all_ids = set(all_objects)
            unused_ids = all_ids - ids_seen
            text = '\n'.join(all_objects[unused_id] for unused_id in sorted(unused_ids))
        else:
            text = '\n'.join(sorted(usages))

        if not text:
            text = '(no usages found)'

        self.result_text.configure(state=tk.NORMAL)
        self.result_text.delete('1.0', tk.END)
        self.result_text.insert('1.0', text)
        self.result_text.configure(state=tk.DISABLED)
