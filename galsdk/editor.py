import pathlib
import tkinter as tk
import tkinter.filedialog as tkfile
import tkinter.messagebox as tkmsg
from tkinter import ttk
from typing import Optional

from direct.showbase.ShowBase import ShowBase
from panda3d.core import getModelPath

from galsdk.project import GameVersion, Project
from galsdk.ui import ActorTab, BackgroundTab, ItemTab, ModelTab, MovieTab, RoomTab, StringTab, VoiceTab


class Editor(ShowBase):
    """The main editor window"""

    project: Optional[Project]

    def __init__(self):
        super().__init__(windowType='none')
        self.project = None

        getModelPath().appendDirectory(pathlib.Path.cwd() / 'models')

        self.startTk()
        self.tkRoot.title('galsdk')

        # top menu
        menu_bar = tk.Menu(self.tkRoot)
        self.tkRoot.config(menu=menu_bar)

        file_menu = tk.Menu(menu_bar, tearoff=False)

        file_menu.add_command(label='New Project...', underline=0, command=self.ask_new_project)
        file_menu.add_command(label='Open Project...', underline=0, command=self.ask_open_project)
        file_menu.add_separator()
        file_menu.add_command(label='Exit', underline=1, command=self.exit)

        menu_bar.add_cascade(label='File', menu=file_menu, underline=0)

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

        image_label.grid(row=0, column=0, sticky=tk.S+tk.E)
        image_path.grid(row=0, column=1, columnspan=4, sticky=tk.S+tk.W)
        game_id_label.grid(row=1, column=0, sticky=tk.E)
        game_id.grid(row=1, column=1, sticky=tk.W)
        region_label.grid(row=2, column=0, sticky=tk.E)
        region.grid(row=2, column=1, sticky=tk.W)
        language_label.grid(row=3, column=0, sticky=tk.E)
        language.grid(row=3, column=1, sticky=tk.W)
        disc_number_label.grid(row=4, column=0, sticky=tk.E)
        disc_number.grid(row=4, column=1, sticky=tk.W)
        demo_text_label.grid(row=5, column=0, sticky=tk.E)
        demo_text.grid(row=5, column=1, sticky=tk.W)
        project_label.grid(row=6, column=0, sticky=tk.E)
        project_path.grid(row=6, column=1, columnspan=3, sticky=tk.E+tk.W)
        browse_project_path.grid(row=6, column=4, sticky=tk.W)
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
        self.notebook.bind('<<NotebookTabChanged>>', self.set_active_tab)

    def ask_new_project(self, *_):
        image_path = tkfile.askopenfilename(filetypes=[('CD images', '*.bin *.img'), ('All files', '*.*')])
        try:
            # TODO: this is slow because we read the whole CD image. find a better way
            version = Project.detect_cd_version(image_path)
        except Exception as e:
            tkmsg.showerror('Failed to open image', str(e))
            return

        self.show_new_project(image_path, version)

    def ask_open_project(self, *_):
        project_dir = tkfile.askdirectory()
        try:
            self.project = Project.open(project_dir)
        except Exception as e:
            tkmsg.showerror('Failed to open project', str(e))
            return

        self.open_project()

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
            # import cProfile
            # profile = cProfile.Profile()
            # profile.enable()
            self.project = Project.create_from_cd(image_path, project_path)
            # profile.disable()
            # profile.dump_stats('stats.dmp')
        except Exception as e:
            tkmsg.showerror('Failed to create project', str(e))
            return

        self.open_project()

    def open_project(self):
        self.default_message.pack_forget()
        self.new_project_view.pack_forget()

        self.makeDefaultPipe()

        self.tabs = [RoomTab(self.project, self), StringTab(self.project), ActorTab(self.project, self),
                     BackgroundTab(self.project), ItemTab(self.project, self), ModelTab(self.project, self),
                     MovieTab(self.project, self), VoiceTab(self.project, self)]
        for tab in self.tabs:
            self.notebook.add(tab, text=tab.name)

        self.notebook.pack(expand=1, fill=tk.BOTH)
        self.set_active_tab()

    def set_active_tab(self, _=None):
        tab_index = self.notebook.index(self.notebook.select())
        for i, tab in enumerate(self.tabs):
            tab.set_active(i == tab_index)

    def exit(self):
        """Exit the editor application"""
        self.destroy()


if __name__ == '__main__':
    editor = Editor()
    editor.run()
