from tkinter import ttk


class Tab(ttk.Frame):
    """A tab in the editor"""

    def __init__(self, name: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name
