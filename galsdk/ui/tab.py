from tkinter import ttk

from galsdk.project import Project


class Tab(ttk.Frame):
    """A tab in the editor"""

    def __init__(self, name: str, project: Project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name
        self.project = project