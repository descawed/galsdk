import json
import pathlib
import tkinter as tk
import tkinter.filedialog as tkfile
import tkinter.messagebox as tkmsg
from functools import partial
from tkinter import ttk
from typing import Optional

from direct.showbase.ShowBase import ShowBase
from panda3d.core import getModelPath

from galsdk.project import Project
from galsdk.game import GameVersion
from galsdk.ui import (ActorTab, AnimationTab, ArtTab, BackgroundTab, ItemTab, MenuTab, ModelTab, MovieTab, RoomTab,
                       StringTab, Tab, VoiceTab)
from galsdk.ui.export import ExportDialog


MAX_RECENT_PROJECTS = 10


class Editor(ShowBase):
    """The main editor window"""

    project: Optional[Project]

    def __init__(self):
        super().__init__(windowType='none')
        self.project = None
        self.project_open_complete = False

        cwd = pathlib.Path.cwd()
        getModelPath().appendDirectory(cwd / 'assets')

        settings_path = cwd / 'editor.json'
        if settings_path.exists():
            with settings_path.open() as f:
                settings = json.load(f)
        else:
            settings = {}
        self.recent_projects = settings.get('recent', [])
        self.saved_geometry = settings.get('geometry')

        self.startTk()

        # top menu
        menu_bar = tk.Menu(self.tkRoot)
        self.tkRoot.config(menu=menu_bar)

        self.file_menu = tk.Menu(menu_bar, tearoff=False)

        self.recent_menu = tk.Menu(self.file_menu, tearoff=False)
        self.populate_recent()

        self.file_menu.add_command(label='New Project...', underline=0, command=self.ask_new_project)
        self.file_menu.add_command(label='Open Project...', underline=0, command=self.ask_open_project)
        self.file_menu.add_cascade(label='Recent', menu=self.recent_menu, underline=0)
        self.file_menu.add_separator()
        self.file_menu.add_command(label='Export...', underline=0, command=self.export_project, state=tk.DISABLED)
        self.file_menu.add_command(label='Save', underline=0, command=self.save_project, state=tk.DISABLED)
        self.file_menu.add_separator()
        self.file_menu.add_command(label='Exit', underline=1, command=self.exit)

        self.tools_menu = tk.Menu(menu_bar, tearoff=False)
        self.tools_menu.add_command(label='Export XA.MXA', command=self.export_xa_mxa, state=tk.DISABLED)

        menu_bar.add_cascade(label='File', menu=self.file_menu, underline=0)
        menu_bar.add_cascade(label='Tools', menu=self.tools_menu, underline=0)

        # tabs for open project (will be populated later)
        self.tabs = []
        self.notebook = ttk.Notebook(self.tkRoot)

        # create new project view
        self.new_project_view = ttk.LabelFrame(self.tkRoot, text='New Project')
        self.game_id_var = tk.StringVar()
        self.region_var = tk.StringVar()
        self.language_var = tk.StringVar()
        self.disc_number_var = tk.StringVar()
        self.demo_text_var = tk.StringVar()
        self.image_path_var = tk.StringVar()
        self.project_path_var = tk.StringVar()
        self.project_path_var.trace_add('write', self.check_create_project_button)

        image_label = ttk.Label(self.new_project_view, text='CD image:', anchor=tk.E)
        image_path = ttk.Label(self.new_project_view, textvariable=self.image_path_var, anchor=tk.W)

        game_id_label = ttk.Label(self.new_project_view, text='Game ID:', anchor=tk.E)
        game_id = ttk.Label(self.new_project_view, textvariable=self.game_id_var, anchor=tk.W)

        region_label = ttk.Label(self.new_project_view, text='Region:', anchor=tk.E)
        region = ttk.Label(self.new_project_view, textvariable=self.region_var, anchor=tk.W)

        language_label = ttk.Label(self.new_project_view, text='Language:', anchor=tk.E)
        language = ttk.Label(self.new_project_view, textvariable=self.language_var, anchor=tk.W)

        disc_number_label = ttk.Label(self.new_project_view, text='Disc #:', anchor=tk.E)
        disc_number = ttk.Label(self.new_project_view, textvariable=self.disc_number_var, anchor=tk.W)

        demo_text_label = ttk.Label(self.new_project_view, text='Demo:', anchor=tk.E)
        demo_text = ttk.Label(self.new_project_view, textvariable=self.demo_text_var, anchor=tk.W)

        project_label = ttk.Label(self.new_project_view, text='Project directory:', anchor=tk.E)
        project_path = ttk.Entry(self.new_project_view, textvariable=self.project_path_var)
        browse_project_path = ttk.Button(self.new_project_view, text='Browse...', command=self.ask_project_dir)

        self.create_project_button = ttk.Button(self.new_project_view, text='Create Project',
                                                command=self.create_project)

        self.new_project_view.grid_rowconfigure(0, weight=1)
        self.new_project_view.grid_rowconfigure(7, weight=1)
        self.new_project_view.grid_columnconfigure(1, weight=1)

        image_label.grid(padx=5, row=0, column=0, sticky=tk.S+tk.E)
        image_path.grid(padx=5, row=0, column=1, columnspan=4, sticky=tk.S+tk.W)
        game_id_label.grid(padx=5, row=1, column=0, sticky=tk.E)
        game_id.grid(padx=5, row=1, column=1, sticky=tk.W)
        region_label.grid(padx=5, row=2, column=0, sticky=tk.E)
        region.grid(padx=5, row=2, column=1, sticky=tk.W)
        language_label.grid(padx=5, row=3, column=0, sticky=tk.E)
        language.grid(padx=5, row=3, column=1, sticky=tk.W)
        disc_number_label.grid(padx=5, row=4, column=0, sticky=tk.E)
        disc_number.grid(padx=5, row=4, column=1, sticky=tk.W)
        demo_text_label.grid(padx=5, row=5, column=0, sticky=tk.E)
        demo_text.grid(padx=5, row=5, column=1, sticky=tk.W)
        project_label.grid(padx=5, row=6, column=0, sticky=tk.E)
        project_path.grid(padx=5, row=6, column=1, columnspan=3, sticky=tk.E+tk.W)
        browse_project_path.grid(padx=5, row=6, column=4, sticky=tk.W)
        self.create_project_button.grid(row=7, column=0, sticky=tk.N+tk.E)

        rows, cols = self.new_project_view.grid_size()
        for i in range(rows):
            self.new_project_view.grid_rowconfigure(i, pad=10)
        for i in range(cols):
            self.new_project_view.grid_columnconfigure(i, minsize=20, pad=5)

        # initial starting view
        self.default_message = ttk.Label(self.tkRoot, text='Open or create a project from the File menu to begin')
        self.default_message.pack(expand=1, fill=tk.BOTH, padx=50, pady=20)

        self.tkRoot.bind('<Control-n>', self.ask_new_project)
        self.tkRoot.bind('<Control-o>', self.ask_open_project)
        self.tkRoot.bind('<Control-s>', self.save_project)
        self.notebook.bind('<<NotebookTabChanged>>', self.set_active_tab)

        self.tkRoot.protocol('WM_DELETE_WINDOW', self.exit)

        self.set_title()
        if self.saved_geometry:
            x = self.saved_geometry['x']
            y = self.saved_geometry['y']
            self.tkRoot.geometry(f'+{x}+{y}')

    def export_xa_mxa(self, *_):
        try:
            self.project.export_xa_mxa()
        except Exception as e:
            tkmsg.showerror('Error', str(e))
        else:
            tkmsg.showinfo('Success', 'XA.MXA and the XDB file have been created in the export directory')

    def set_title(self):
        if self.project is None:
            title = 'galsdk'
        else:
            project_dir = str(self.project.project_dir)
            title = f'galsdk - {project_dir}'

        if any(tab.has_unsaved_changes for tab in self.tabs):
            title = '* ' + title

        self.tkRoot.title(title)

    def ask_new_project(self, *_):
        image_path = tkfile.askopenfilename(filetypes=[('CD images', '*.bin *.img'), ('All files', '*.*')])
        if not image_path:
            return

        try:
            # TODO: this is slow because we read the whole CD image. find a better way
            version = Project.detect_cd_version(image_path)
        except Exception as e:
            tkmsg.showerror('Failed to open image', str(e))
            return

        self.show_new_project(image_path, version)

    def ask_open_project(self, *_):
        project_dir = tkfile.askdirectory()
        if not project_dir:
            return

        try:
            project = Project.open(project_dir)
        except Exception as e:
            tkmsg.showerror('Failed to open project', str(e))
            return

        self.open_project(project)

    def ask_project_dir(self):
        project_dir = tkfile.askdirectory(mustexist=False)
        self.project_path_var.set(project_dir)

    def check_create_project_button(self, *_):
        if self.project_path_var.get() != '':
            self.create_project_button['state'] = tk.NORMAL
        else:
            self.create_project_button['state'] = tk.DISABLED

    def show_new_project(self, image_path: str, version: GameVersion):
        self.image_path_var.set(image_path)
        self.game_id_var.set(version.id)
        self.region_var.set(version.region)
        self.language_var.set(version.language)
        self.disc_number_var.set(str(version.disc))
        self.demo_text_var.set('Yes' if version.is_demo else 'No')
        self.project_path_var.set('')

        self.default_message.pack_forget()
        self.notebook.pack_forget()
        self.new_project_view.pack(expand=1, fill=tk.BOTH, padx=5, pady=(0, 5))

    def create_project(self):
        image_path = self.image_path_var.get()
        project_path = self.project_path_var.get()
        try:
            project = Project.create_from_cd(image_path, project_path)
        except Exception as e:
            tkmsg.showerror('Failed to create project', str(e))
            return

        self.open_project(project)

    def open_project(self, project: Project):
        first_open = self.project is None
        self.project = project
        self.project_open_complete = False

        self.default_message.pack_forget()
        self.new_project_view.pack_forget()

        if self.pipe is None:
            self.makeDefaultPipe()
        for tab in self.tabs:
            tab.close()
        for tab in self.notebook.tabs():
            self.notebook.forget(tab)

        tabs = [RoomTab(self.project, self), StringTab(self.project), ActorTab(self.project, self),
                AnimationTab(self.project, self), BackgroundTab(self.project), ItemTab(self.project, self),
                ModelTab(self.project, self), ArtTab(self.project), MenuTab(self.project), MovieTab(self.project, self),
                VoiceTab(self.project, self)]
        self.tabs = []
        for tab in tabs:
            if tab.should_appear:
                self.notebook.add(tab, text=tab.name)
                tab.on_change(self.on_tab_change)
                self.tabs.append(tab)

        self.notebook.pack(expand=1, fill=tk.BOTH)

        if self.saved_geometry and first_open:
            width = self.saved_geometry['width']
            height = self.saved_geometry['height']
            self.tkRoot.geometry(f'{width}x{height}')

        self.set_active_tab()

        project_dir = str(self.project.project_dir)
        if project_dir in self.recent_projects:
            self.recent_projects.remove(project_dir)
        self.recent_projects.append(project_dir)
        if len(self.recent_projects) > MAX_RECENT_PROJECTS:
            del self.recent_projects[:-MAX_RECENT_PROJECTS]
        self.populate_recent()
        self.save_settings()

        self.set_title()

        self.file_menu.entryconfigure(4, state=tk.NORMAL)
        self.file_menu.entryconfigure(5, state=tk.NORMAL)
        self.tools_menu.entryconfigure(1, state=tk.NORMAL)

        self.project_open_complete = True

    def on_tab_change(self, tab: Tab):
        num_tabs = self.notebook.index('end')
        for i in range(num_tabs):
            text = self.notebook.tab(i, 'text')
            if text in [tab.name, f'* {tab.name}']:
                new_name = tab.name
                if tab.has_unsaved_changes:
                    new_name = '* ' + new_name
                self.notebook.tab(i, text=new_name)
                break
        self.set_title()

    def save_project(self, *_):
        if not self.project:
            return

        for tab in self.tabs:
            tab.save()

        # remove change markers from any tabs that have them
        num_tabs = self.notebook.index('end')
        for i in range(num_tabs):
            text = self.notebook.tab(i, 'text')
            if text.startswith('* '):
                self.notebook.tab(i, text=text[2:])
        self.set_title()

    def export_project(self, *_):
        if not self.project:
            return

        x = self.tkRoot.winfo_rootx()
        y = self.tkRoot.winfo_rooty()
        width = self.tkRoot.winfo_width()
        dialog_width = min(1000, int(width*0.9))
        dialog_x = x + width // 2 - dialog_width // 2
        dialog = ExportDialog(self.tkRoot, self.project)
        dialog.geometry(f'{dialog_width}x1000+{dialog_x}+{y}')
        dialog.grab_set()

    def populate_recent(self):
        self.recent_menu.delete(0, 'end')
        for path in reversed(self.recent_projects):
            path = pathlib.Path(path)
            # we use functools.partial to make sure the call is bound to the value of path as of this iteration, instead
            # of its value at the end of the function
            self.recent_menu.add_command(label=path.name,
                                         command=partial(lambda p, *_: self.open_project(Project.open(p)), str(path)))

    def save_settings(self):
        with (pathlib.Path.cwd() / 'editor.json').open('w') as f:
            json.dump({
                'recent': self.recent_projects,
                'geometry': self.saved_geometry,
            }, f)

    def set_active_tab(self, _=None):
        tab_index = self.notebook.index(self.notebook.select())
        for i, tab in enumerate(self.tabs):
            tab.set_active(i == tab_index)

    def exit(self):
        """Exit the editor application"""
        if any(tab.has_unsaved_changes for tab in self.tabs):
            confirm = tkmsg.askyesno('Unsaved changes',
                                     'You have unsaved changes. Do you want to quit without saving?')
            if not confirm:
                return

        if self.project and self.project_open_complete:
            # if a project is open, save the current window position and size
            width = self.tkRoot.winfo_width()
            height = self.tkRoot.winfo_height()
            x = self.tkRoot.winfo_rootx()
            y = self.tkRoot.winfo_rooty()
            self.saved_geometry = {'width': width, 'height': height, 'x': x, 'y': y}
            self.save_settings()

        self.tkRoot.destroy()


if __name__ == '__main__':
    editor = Editor()
    editor.run()
