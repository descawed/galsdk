from __future__ import annotations

from typing import TextIO


class Config(dict):
    """PSX configuration file (SYSTEM.CNF)"""

    @classmethod
    def read(cls, source: TextIO) -> Config:
        config = cls()
        for line in source:
            # if the line has any content
            if line.strip():
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()

        return config

    def write(self, destination: TextIO):
        for key, value in self.items():
            destination.write(f'{key} = {value}\n')

    @property
    def boot(self) -> str:
        return self['BOOT']

    @boot.setter
    def boot(self, value: str):
        self['BOOT'] = value

    @property
    def tcb(self) -> int:
        return int(self['TCB'])

    @tcb.setter
    def tcb(self, value: int):
        self['TCB'] = str(value)

    @property
    def event(self) -> int:
        return int(self['EVENT'])

    @event.setter
    def event(self, value: int):
        self['EVENT'] = str(value)

    @property
    def stack(self) -> int:
        return int(self['STACK'], 16)

    @stack.setter
    def stack(self, value: int):
        self['STACK'] = f'{value:08x}'
