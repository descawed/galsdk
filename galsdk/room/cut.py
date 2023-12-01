from panda3d.core import CollisionEntry, GeomNode, Mat3, NodePath, Point3, Vec3

from galsdk import graphics
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
        centroid = self.calculate_centroid()
        self.relative_p1 = self.p1 - centroid
        self.relative_p2 = self.p2 - centroid
        self.relative_p3 = self.p3 - centroid
        self.relative_p4 = self.p4 - centroid

        super().__init__(name, self.calculate_centroid(), 0)
        self.color = CUT_COLOR
        self.resize_vertices = []
        self.resize_offset = 0

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
        geom = graphics.make_quad(
            (self.p1.panda_x - self.position.panda_x, self.p1.panda_y - self.position.panda_y),
            (self.p2.panda_x - self.position.panda_x, self.p2.panda_y - self.position.panda_y),
            (self.p4.panda_x - self.position.panda_x, self.p4.panda_y - self.position.panda_y),
            (self.p3.panda_x - self.position.panda_x, self.p3.panda_y - self.position.panda_y),
            is_static=False,
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

    @property
    def vertices(self) -> list[Point3]:
        return [
            self.relative_p1.panda_point,
            self.relative_p2.panda_point,
            self.relative_p4.panda_point,
            self.relative_p3.panda_point,
        ]

    def set_relative(self, p1: Point3, p2: Point3, p3: Point3, p4: Point3):
        vdata = self.original_model.node().modifyGeom(0).modifyVertexData()
        graphics.update_quad(vdata, p1, p2, p4, p3)
        self.relative_p1.panda_point = p1
        self.relative_p2.panda_point = p2
        self.relative_p3.panda_point = p3
        self.relative_p4.panda_point = p4
        panda_position = self.position.panda_point
        self.p1.panda_point = p1 + panda_position
        self.p2.panda_point = p2 + panda_position
        self.p3.panda_point = p3 + panda_position
        self.p4.panda_point = p4 + panda_position
        self.notify_transform()

    def move(self, direction: Vec3):
        super().move(direction)
        pos = self.node_path.getPos()
        self.p1.panda_point = self.relative_p1.panda_point + pos
        self.p2.panda_point = self.relative_p2.panda_point + pos
        self.p3.panda_point = self.relative_p3.panda_point + pos
        self.p4.panda_point = self.relative_p4.panda_point + pos
        self.notify_transform()

    def rotate(self, angle: float):
        rotate_mat = Mat3.rotateMat(angle)
        p1 = rotate_mat.xform(self.relative_p1.panda_point)
        p2 = rotate_mat.xform(self.relative_p2.panda_point)
        p3 = rotate_mat.xform(self.relative_p3.panda_point)
        p4 = rotate_mat.xform(self.relative_p4.panda_point)
        self.set_relative(p1, p2, p3, p4)

    def get_pos_cursor_type(self, camera: NodePath, entry: CollisionEntry) -> Cursor | None:
        scale_mat = Mat3.scaleMat(Vec3(CENTER_AREA, CENTER_AREA, CENTER_AREA))
        p1_scaled = scale_mat.xform(self.relative_p1.panda_point)
        p2_scaled = scale_mat.xform(self.relative_p2.panda_point)
        p3_scaled = scale_mat.xform(self.relative_p3.panda_point)
        p4_scaled = scale_mat.xform(self.relative_p4.panda_point)

        center_p1 = Point()
        center_p1.panda_point = p1_scaled

        center_p2 = Point()
        center_p2.panda_point = p2_scaled

        center_p3 = Point()
        center_p3.panda_point = p3_scaled

        center_p4 = Point()
        center_p4.panda_point = p4_scaled

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

    def start_resize(self, entry: CollisionEntry):
        self.resize_vertices, self.resize_offset = self.get_edge(entry, self.vertices)

    def resize(self, point: Point3):
        # FIXME: there's some inaccuracy here that results in the cut changing its size in ways that it shouldn't while
        #  being resized
        corners = self.vertices

        game_point = Point()
        game_point.panda_x = point[0]
        game_point.panda_y = point[1]
        line = Line2d(Point(), game_point)  # relative center is at (0, 0)
        final_point = line.get_point_at_distance(line.panda_len + self.resize_offset).panda_point

        if len(self.resize_vertices) == 1:
            corners[self.resize_vertices[0]] = final_point
        else:
            # we're moving an edge, so we're resizing in one dimension
            index1, index2 = self.resize_vertices
            vert1 = corners[index1]
            vert2 = corners[index2]
            # find the equation of the line passing through final_point with the same slope as the edge
            if vert1[0] == vert2[0]:
                a = 1
                b = 0
                c = -final_point[0]
            else:
                m = (vert1[1] - vert2[1]) / (vert1[0] - vert2[0])
                a = -m
                b = 1
                c = m * final_point[0] - final_point[1]
            # https://en.wikipedia.org/wiki/Distance_from_a_point_to_a_line#Line_defined_by_an_equation
            # for each vertex, find the point on that line closest to the vertex, and that will be the new vertex
            denom = a**2 + b**2
            for vert in [vert1, vert2]:
                ay = a * vert[1]
                bx = b * vert[0]
                vert[0] = (b*(bx - ay) - a*c)/denom
                vert[1] = (a*(ay - bx) - b*c)/denom

        self.set_relative(corners[0], corners[1], corners[3], corners[2])
