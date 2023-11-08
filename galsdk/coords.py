from __future__ import annotations

import functools
import math

from panda3d.core import Point3


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

    def __abs__(self) -> Dimension:
        return Dimension(abs(self.game_units), self.is_mirrored)

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

    def __repr__(self) -> str:
        return f'Dimension({self.game_units}, {self.is_mirrored})'

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

    def __add__(self, other: Point) -> Point:
        return Point(self.game_x + other.game_x, self.game_y + other.game_y, self.game_z + other.game_z)

    def __iadd__(self, other: Point):
        self.game_x += other.game_x
        self.game_y += other.game_y
        self.game_z += other.game_z

    def __sub__(self, other: Point) -> Point:
        return Point(self.game_x - other.game_x, self.game_y - other.game_y, self.game_z - other.game_z)

    def __isub__(self, other: Point):
        self.game_x -= other.game_x
        self.game_y -= other.game_y
        self.game_z -= other.game_z

    def __repr__(self) -> str:
        return f'Point({self.game_x}, {self.game_y}, {self.game_z})'

    def find_midpoint(self, other: Point) -> Point:
        # we do the calculation in panda units to preserve float accuracy until the end
        point = Point()
        point.x.panda_units = self.panda_x + (other.panda_x - self.panda_x) / 2
        point.y.panda_units = self.panda_y + (other.panda_y - self.panda_y) / 2
        point.z.panda_units = self.panda_z + (other.panda_z - self.panda_z) / 2
        return point

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

    @property
    def panda_point(self) -> Point3:
        return Point3(self.panda_x, self.panda_y, self.panda_z)

    @panda_point.setter
    def panda_point(self, value: Point3):
        self.panda_x = value[0]
        self.panda_y = value[1]
        self.panda_z = value[2]


class Line2d:
    def __init__(self, a: Point, b: Point):
        self.a = a
        self.b = b

    def find_intersection(self, other: Line2d) -> Point:
        a1 = (self.a.panda_x, self.a.panda_y)
        a2 = (self.b.panda_x, self.b.panda_y)
        b1 = (other.a.panda_x, other.a.panda_y)
        b2 = (other.b.panda_x, other.b.panda_y)

        try:
            am = (a2[1] - a1[1]) / (a2[0] - a1[0])
        except ZeroDivisionError:
            am = 0.
        ab = a1[1] - am * a1[0]
        try:
            bm = (b2[1] - b1[1]) / (b2[0] - b1[0])
        except ZeroDivisionError:
            bm = 0.
        bb = b1[1] - bm * b1[0]

        point = Point()
        try:
            point.panda_x = (bb - ab) / (am - bm)
        except ZeroDivisionError:
            pass
        point.panda_y = am * point.panda_x + ab
        return point

    @property
    def panda_len(self) -> float:
        diff = self.b - self.a
        return math.sqrt(diff.panda_x**2 + diff.panda_y**2)

    def get_point_at_distance(self, dt: float) -> Point:
        # https://math.stackexchange.com/a/1630886
        d = self.panda_len
        t = dt / d
        p = Point()
        p.panda_x = (1 - t)*self.a.panda_x + t*self.b.panda_x
        p.panda_y = (1 - t)*self.a.panda_y + t*self.b.panda_y
        return p


class Triangle2d:
    def __init__(self, p1: Point, p2: Point, p3: Point):
        self.p1 = p1
        self.p2 = p2
        self.p3 = p3

    @property
    def centroid(self) -> Point:
        m12 = self.p1.find_midpoint(self.p2)
        m23 = self.p2.find_midpoint(self.p3)

        line1 = Line2d(m12, self.p3)
        line2 = Line2d(self.p1, m23)
        return line1.find_intersection(line2)

    @staticmethod
    def sign(p1: Point, p2: Point, p3: Point) -> float:
        return ((p1.panda_x - p3.panda_x) * (p2.panda_y - p3.panda_y)
                - (p2.panda_x - p3.panda_x) * (p1.panda_y - p3.panda_y))

    def is_point_within(self, p: Point) -> bool:
        # https://stackoverflow.com/a/2049593
        d1 = self.sign(p, self.p1, self.p2)
        d2 = self.sign(p, self.p2, self.p3)
        d3 = self.sign(p, self.p3, self.p1)

        return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))
