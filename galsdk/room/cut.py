from panda3d.core import Geom

from galsdk.coords import Line2d, Point, Triangle2d
from galsdk.module import CameraCut
from galsdk.room.object import RoomObject


CUT_COLOR = (1., 0.65, 0., 0.5)


class CameraCutObject(RoomObject):
    def __init__(self, name: str, cut: CameraCut):
        self.camera_id = cut.index
        self.p1 = Point(cut.x1, 0, cut.z1)
        self.p2 = Point(cut.x2, 0, cut.z2)
        self.p3 = Point(cut.x3, 0, cut.z3)
        self.p4 = Point(cut.x4, 0, cut.z4)

        triangle1 = Triangle2d(self.p1, self.p2, self.p3)
        triangle2 = Triangle2d(self.p1, self.p3, self.p4)
        triangle3 = Triangle2d(self.p1, self.p2, self.p4)
        triangle4 = Triangle2d(self.p2, self.p3, self.p4)

        line1 = Line2d(triangle1.centroid, triangle2.centroid)
        line2 = Line2d(triangle3.centroid, triangle4.centroid)

        quad_centroid = line1.find_intersection(line2)
        super().__init__(name, quad_centroid, 0)
        self.color = CUT_COLOR

    def get_model(self) -> Geom:
        return self._make_quad(
            (self.p1.panda_x - self.position.panda_x, self.p1.panda_y - self.position.panda_y),
            (self.p2.panda_x - self.position.panda_x, self.p2.panda_y - self.position.panda_y),
            (self.p4.panda_x - self.position.panda_x, self.p4.panda_y - self.position.panda_y),
            (self.p3.panda_x - self.position.panda_x, self.p3.panda_y - self.position.panda_y),
        )
