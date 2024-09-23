from typing import Callable


class Replaceable[T]:
    def __init__(self, obj: T, replace_callback: Callable[[T], None]):
        self._object = obj
        self._replace_callback = replace_callback

    @property
    def object(self) -> T:
        return self._object

    @object.setter
    def object(self, value: T):
        self._object = value
        self._replace_callback(value)
