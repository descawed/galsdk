import math

from panda3d.core import Geom, Point3

from galsdk.model import SCALE_FACTOR
from galsdk.module import RectangleCollider, TriangleCollider
from galsdk.room.object import RoomObject


COLLIDER_COLOR = (0, 255, 0, 127)


class RectangleColliderObject(RoomObject):
    def __init__(self, bounds: RectangleCollider):
        center_x = (bounds.x_pos + bounds.x_size / 2) / SCALE_FACTOR
        # z in the game's coordinate system, y in ours
        center_y = (bounds.z_pos + bounds.z_size / 2) / SCALE_FACTOR
        super().__init__(center_x, center_y, 0, 0)
        self.bounds = bounds
        self.color = COLLIDER_COLOR

    def get_model(self) -> Geom:
        half_x = self.bounds.x_size / 2 / SCALE_FACTOR
        half_z = self.bounds.z_size / 2 / SCALE_FACTOR
        return self._make_quad((-half_x, -half_z), (half_x, -half_z), (half_x, half_z), (-half_x, half_z), self.color)

    @property
    def size(self) -> tuple[float, float]:
        return self.bounds.x_size / SCALE_FACTOR, self.bounds.z_size / SCALE_FACTOR


class WallColliderObject(RectangleColliderObject):
    def __init__(self, bounds: RectangleCollider):
        super().__init__(bounds)
        self.color = (255, 0, 0, 255)


class TriangleColliderObject(RoomObject):
    def __init__(self, bounds: TriangleCollider):
        self.bounds = bounds
        self.color = COLLIDER_COLOR
        centroid = self.centroid
        super().__init__(centroid[0], centroid[1], 0, 0)

    def get_model(self) -> Geom:
        centroid = self.centroid
        p1 = self.p1
        p2 = self.p2
        p3 = self.p3
        return self._make_triangle(
            (p1[0] - centroid[0], p1[1] - centroid[1]),
            (p2[0] - centroid[0], p2[1] - centroid[1]),
            (p3[0] - centroid[0], p3[1] - centroid[1]),
            self.color,
        )

    @staticmethod
    def _find_midpoint(p1: tuple[float, float], p2: tuple[float, float]) -> tuple[float, float]:
        x = p1[0] + (p2[0] - p1[0]) / 2
        y = p1[1] + (p2[1] - p1[1]) / 2
        return x, y
    
    @staticmethod
    def _find_intersection(a1: tuple[float, float], a2: tuple[float, float],
                           b1: tuple[float, float], b2: tuple[float, float]) -> tuple[float, float]:
        am = (a2[1] - a1[1]) / (a2[0] - a1[0])
        ab = a1[1] - am*a1[0]
        bm = (b2[1] - b1[1]) / (b2[0] - b1[0])
        bb = b1[1] - bm*b1[0]

        x = (bb - ab)/(am - bm)
        y = am*x + ab
        return x, y

    @property
    def centroid(self) -> tuple[float, float]:
        p1 = self.p1
        p2 = self.p2
        p3 = self.p3

        m12 = self._find_midpoint(p1, p2)
        m23 = self._find_midpoint(p2, p3)

        return self._find_intersection(m12, p3, p1, m23)

    @property
    def p1(self) -> tuple[float, float]:
        return self.bounds.x1 / SCALE_FACTOR, self.bounds.z1 / SCALE_FACTOR

    @property
    def p2(self) -> tuple[float, float]:
        return self.bounds.x2 / SCALE_FACTOR, self.bounds.z2 / SCALE_FACTOR

    @property
    def p3(self) -> tuple[float, float]:
        return self.bounds.x3 / SCALE_FACTOR, self.bounds.z3 / SCALE_FACTOR
