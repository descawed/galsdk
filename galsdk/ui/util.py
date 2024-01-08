import tkinter as tk
from typing import Callable, Literal


def validate_int(value: str, base: int = 10) -> bool:
    if value == '':
        return True

    try:
        int(value, base)
        return True
    except ValueError:
        return False


def validate_float(value: str) -> bool:
    if value == '':
        return True

    try:
        float(value)
        return True
    except ValueError:
        return False


class StringVar(tk.StringVar):
    def __init__(self, master: tk.Misc = None, value: str = None, name: str = None):
        super().__init__(master, value, name)
        self.__traces = []

    def trace_add(self, mode: Literal["array", "read", "write", "unset"],
                  callback: Callable[[str, str, str], object]) -> str:
        result = super().trace_add(mode, callback)
        self.__traces.append((mode, callback))
        return result

    def set_no_trace(self, value: str):
        for mode, name in self.trace_info():
            self.trace_remove(mode[0], name)
        self.set(value)
        for mode, callback in self.__traces:
            super().trace_add(mode, callback)
