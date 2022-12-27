from __future__ import annotations

import functools


@functools.total_ordering
class Dimension:
    SCALE_FACTOR = 64

    def __init__(self, initial_value: int = 0, is_mirrored: bool = False):
        self._game_units = 0
        self._panda_units = 0.
        self.is_mirrored = is_mirrored
        if initial_value != 0:
            self.game_units = initial_value

    def __neg__(self):
        return Dimension(-self.game_units, self.is_mirrored)

    def __pos__(self):
        return Dimension(self.game_units, self.is_mirrored)

    def __add__(self, other: Dimension):
        if other.is_mirrored != self.is_mirrored:
            raise ValueError('Attempted to add incompatible dimensions')
        return Dimension(self.game_units + other.game_units, self.is_mirrored)

    def __iadd__(self, other: Dimension):
        if other.is_mirrored != self.is_mirrored:
            raise ValueError('Attempted to add incompatible dimensions')
        self.game_units += other.game_units

    def __sub__(self, other: Dimension):
        if other.is_mirrored != self.is_mirrored:
            raise ValueError('Attempted to subtract incompatible dimensions')
        return Dimension(self.game_units - other.game_units, self.is_mirrored)

    def __isub__(self, other: Dimension):
        if other.is_mirrored != self.is_mirrored:
            raise ValueError('Attempted to subtract incompatible dimensions')
        self.game_units -= other.game_units

    def __mul__(self, other: Dimension | int | float):
        if isinstance(other, Dimension):
            if other.is_mirrored != self.is_mirrored:
                raise ValueError('Attempted to multiply incompatible dimensions')
            return Dimension(self.game_units * other.game_units, self.is_mirrored)
        return Dimension(int(self.game_units * other), self.is_mirrored)

    def __imul__(self, other: Dimension | int | float):
        if isinstance(other, Dimension):
            if other.is_mirrored != self.is_mirrored:
                raise ValueError('Attempted to multiply incompatible dimensions')
            self.game_units *= other.game_units
        else:
            self.game_units = int(self.game_units * other)

    def __truediv__(self, other: Dimension | int | float):
        if isinstance(other, Dimension):
            if other.is_mirrored != self.is_mirrored:
                raise ValueError('Attempted to divide incompatible dimensions')
            return Dimension(int(self.game_units / other.game_units), self.is_mirrored)
        return Dimension(int(self.game_units / other), self.is_mirrored)

    def __itruediv__(self, other: Dimension | int | float):
        if isinstance(other, Dimension):
            if other.is_mirrored != self.is_mirrored:
                raise ValueError('Attempted to divide incompatible dimensions')
            self.game_units = int(self.game_units / other.game_units)
        else:
            self.game_units = int(self.game_units / other)

    def __floordiv__(self, other: Dimension | int | float):
        if isinstance(other, Dimension):
            if other.is_mirrored != self.is_mirrored:
                raise ValueError('Attempted to divide incompatible dimensions')
            return Dimension(self.game_units // other.game_units, self.is_mirrored)
        return Dimension(int(self.game_units // other), self.is_mirrored)

    def __ifloordiv__(self, other: Dimension | int | float):
        if isinstance(other, Dimension):
            if other.is_mirrored != self.is_mirrored:
                raise ValueError('Attempted to divide incompatible dimensions')
            self.game_units = self.game_units // other.game_units
        else:
            self.game_units = int(self.game_units // other)

    def __mod__(self, other: Dimension | int):
        if isinstance(other, Dimension):
            if other.is_mirrored != self.is_mirrored:
                raise ValueError('Attempted to divide incompatible dimensions')
            return Dimension(self.game_units % other.game_units, self.is_mirrored)
        return Dimension(self.game_units % other, self.is_mirrored)

    def __imod__(self, other: Dimension | int):
        if isinstance(other, Dimension):
            if other.is_mirrored != self.is_mirrored:
                raise ValueError('Attempted to divide incompatible dimensions')
            self.game_units %= other.game_units
        else:
            self.game_units %= other

    def __lt__(self, other: Dimension):
        if other.is_mirrored != self.is_mirrored:
            raise ValueError('Attempted to compare incompatible dimensions')
        return self.game_units < other.game_units

    def __eq__(self, other: Dimension):
        return self.game_units == other.game_units and self.is_mirrored == other.is_mirrored

    @property
    def game_units(self) -> int:
        return self._game_units

    @game_units.setter
    def game_units(self, value: int):
        self._game_units = value
        self._panda_units = value / self.SCALE_FACTOR
        if self.is_mirrored:
            self._panda_units = -self.panda_units

    @property
    def panda_units(self) -> float:
        return self._panda_units

    @panda_units.setter
    def panda_units(self, value: float):
        self._game_units = int(value * self.SCALE_FACTOR)
        # game units are what ultimately get stored and loaded, so ensure panda units are always based off game units
        self._panda_units = self._game_units / self.SCALE_FACTOR
        if self.is_mirrored:
            self._game_units = -self.game_units


class Point:
    def __init__(self, x: int = 0, y: int = 0, z: int = 0):
        self.x = Dimension(x, True)
        self.y = Dimension(z)
        self.z = Dimension(y)

    def __add__(self, other: Point):
        return Point(self.game_x + other.game_x, self.game_y + other.game_y, self.game_z + other.game_z)

    def __iadd__(self, other: Point):
        self.game_x += other.game_x
        self.game_y += other.game_y
        self.game_z += other.game_z

    def __sub__(self, other: Point):
        return Point(self.game_x - other.game_x, self.game_y - other.game_y, self.game_z - other.game_z)

    def __isub__(self, other: Point):
        self.game_x -= other.game_x
        self.game_y -= other.game_y
        self.game_z -= other.game_z

    @property
    def game_x(self) -> int:
        return self.x.game_units

    @game_x.setter
    def game_x(self, value: int):
        self.x.game_units = value

    @property
    def game_y(self) -> int:
        return self.z.game_units

    @game_y.setter
    def game_y(self, value: int):
        self.z.game_units = value

    @property
    def game_z(self) -> int:
        return self.y.game_units

    @game_z.setter
    def game_z(self, value: int):
        self.y.game_units = value

    @property
    def panda_x(self) -> float:
        return self.x.panda_units

    @panda_x.setter
    def panda_x(self, value: float):
        self.x.panda_units = value

    @property
    def panda_y(self) -> float:
        return self.y.panda_units

    @panda_y.setter
    def panda_y(self, value: float):
        self.y.panda_units = value

    @property
    def panda_z(self) -> float:
        return self.z.panda_units

    @panda_z.setter
    def panda_z(self, value: float):
        self.z.panda_units = value
