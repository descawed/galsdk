from panda3d.core import CollisionEntry, GeomNode, NodePath, Vec3

from galsdk import util
from galsdk.coords import Line2d, Point, Triangle2d
from galsdk.module import CameraCut
from galsdk.room.object import RoomObject
from galsdk.ui.viewport import Cursor

CUT_COLOR = (1., 0.65, 0., 0.5)
CENTER_AREA = 0.9


class CameraCutObject(RoomObject):
    def __init__(self, name: str, cut: CameraCut):
        self.camera_id = cut.index
        self.p1 = Point(cut.x1, 0, cut.z1)
        self.p2 = Point(cut.x2, 0, cut.z2)
        self.p3 = Point(cut.x3, 0, cut.z3)
        self.p4 = Point(cut.x4, 0, cut.z4)

        super().__init__(name, self.calculate_centroid(), 0)
        self.color = CUT_COLOR

    def calculate_centroid(self) -> Point:
        triangle1 = Triangle2d(self.p1, self.p2, self.p3)
        triangle2 = Triangle2d(self.p1, self.p3, self.p4)
        triangle3 = Triangle2d(self.p1, self.p2, self.p4)
        triangle4 = Triangle2d(self.p2, self.p3, self.p4)

        line1 = Line2d(triangle1.centroid, triangle2.centroid)
        line2 = Line2d(triangle3.centroid, triangle4.centroid)

        return line1.find_intersection(line2)

    def recalculate_center(self):
        centroid = self.calculate_centroid()
        self.position.x = centroid.x
        self.position.y = centroid.y

    def add_to_scene(self, scene: NodePath):
        super().add_to_scene(scene)
        # vertices are not in a consistent order in the game data
        self.node_path.setTwoSided(True)

    def get_model(self) -> NodePath:
        geom = util.make_quad(
            (self.p1.panda_x - self.position.panda_x, self.p1.panda_y - self.position.panda_y),
            (self.p2.panda_x - self.position.panda_x, self.p2.panda_y - self.position.panda_y),
            (self.p4.panda_x - self.position.panda_x, self.p4.panda_y - self.position.panda_y),
            (self.p3.panda_x - self.position.panda_x, self.p3.panda_y - self.position.panda_y),
        )

        node = GeomNode('cut_quad')
        node.addGeom(geom)
        return NodePath(node)

    def as_camera_cut(self) -> CameraCut:
        return CameraCut(self.camera_id, self.p1.game_x, self.p1.game_z, self.p2.game_x, self.p2.game_z,
                         self.p3.game_x, self.p3.game_z, self.p4.game_x, self.p4.game_z)

    @property
    def is_2d(self) -> bool:
        return True

    @property
    def can_resize(self) -> bool:
        return True

    @property
    def can_rotate(self) -> bool:
        return True

    def get_pos_cursor_type(self, camera: NodePath, entry: CollisionEntry) -> Cursor | None:
        center_p1 = Point()
        center_p1.panda_x = (self.p1.panda_x - self.position.panda_x) * CENTER_AREA
        center_p1.panda_y = (self.p1.panda_y - self.position.panda_y) * CENTER_AREA

        center_p2 = Point()
        center_p2.panda_x = (self.p2.panda_x - self.position.panda_x) * CENTER_AREA
        center_p2.panda_y = (self.p2.panda_y - self.position.panda_y) * CENTER_AREA

        center_p3 = Point()
        center_p3.panda_x = (self.p3.panda_x - self.position.panda_x) * CENTER_AREA
        center_p3.panda_y = (self.p3.panda_y - self.position.panda_y) * CENTER_AREA

        center_p4 = Point()
        center_p4.panda_x = (self.p4.panda_x - self.position.panda_x) * CENTER_AREA
        center_p4.panda_y = (self.p4.panda_y - self.position.panda_y) * CENTER_AREA

        center_tri1 = Triangle2d(center_p1, center_p2, center_p4)
        center_tri2 = Triangle2d(center_p4, center_p3, center_p1)

        rel_intersection = entry.getSurfacePoint(self.node_path)
        rel_point = Point()
        rel_point.panda_x = rel_intersection[0]
        rel_point.panda_y = rel_intersection[1]

        if center_tri1.is_point_within(rel_point) or center_tri2.is_point_within(rel_point):
            return Cursor.CENTER

        vertices = [Vec3(center_p1.panda_x, center_p1.panda_y, 0), Vec3(center_p2.panda_x, center_p2.panda_y, 0),
                    Vec3(center_p4.panda_x, center_p4.panda_y, 0), Vec3(center_p3.panda_x, center_p3.panda_y, 0)]
        angle = self.get_cursor_angle(camera, entry, vertices)
        return Cursor.from_angle(angle)
