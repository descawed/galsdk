from __future__ import annotations

from tkinter import ttk
from typing import Callable

from galsdk.project import Project


class Tab(ttk.Frame):
    """A tab in the editor"""

    def __init__(self, name: str, project: Project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name
        self.project = project
        self.tab_change_listeners = []

    def set_active(self, is_active: bool):
        pass

    @property
    def should_appear(self) -> bool:
        return True

    @property
    def has_unsaved_changes(self) -> bool:
        return False

    def save(self):
        pass

    def on_change(self, listener: Callable[[Tab], None]):
        self.tab_change_listeners.append(listener)

    def notify_change(self):
        for listener in self.tab_change_listeners:
            listener(self)

    def close(self):
        pass
