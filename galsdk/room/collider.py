import math

from panda3d.core import CollisionEntry, GeomNode, Mat3, NodePath, Point2, SamplerState, Texture, Vec3, Point3
from PIL import Image, ImageDraw

from galsdk import util
from galsdk.coords import Dimension, Line2d, Point, Triangle2d
from galsdk.module import CircleCollider, RectangleCollider, TriangleCollider
from galsdk.room.object import RoomObject
from galsdk.ui.viewport import Cursor

COLLIDER_COLOR = (0., 1., 0., 0.5)
CENTER_AREA = 0.9


class RectangleColliderObject(RoomObject):
    def __init__(self, name: str, bounds: RectangleCollider):
        center_x = bounds.x_pos + bounds.x_size // 2
        center_z = bounds.z_pos + bounds.z_size // 2
        super().__init__(name, Point(center_x, 0, center_z), 0.)
        self.width = Dimension(bounds.x_size, True)
        self.height = Dimension(bounds.z_size)
        self.unknown = bounds.unknown
        self.color = COLLIDER_COLOR
        self.is_wall = False
        self.resize_vertices = []
        self.resize_offset = 0

    def get_model(self) -> NodePath:
        half_x = (self.width / 2).panda_units
        half_z = (self.height / 2).panda_units
        geom = util.make_quad((-half_x, -half_z), (half_x, -half_z), (half_x, half_z), (-half_x, half_z))
        node = GeomNode('rectangle_collider_quad')
        node.addGeom(geom)
        return NodePath(node)

    def add_to_scene(self, scene: NodePath):
        super().add_to_scene(scene)
        self.node_path.setTwoSided(True)

    @property
    def x_pos(self) -> Dimension:
        return self.position.x - self.width // 2

    @x_pos.setter
    def x_pos(self, value: Dimension):
        self.position.x = value + self.width // 2

    @property
    def x_far(self) -> Dimension:
        return self.x_pos + self.width

    @property
    def z_pos(self) -> Dimension:
        return self.position.y - self.height // 2

    @z_pos.setter
    def z_pos(self, value: Dimension):
        self.position.y = value + self.height // 2

    @property
    def z_far(self) -> Dimension:
        return self.z_pos + self.height

    def set_width(self, value: Dimension):
        center_x = self.x_pos + value // 2
        self.position.x = center_x
        self.width = value

    def set_height(self, value: Dimension):
        center_z = self.z_pos + value // 2
        self.position.y = center_z
        self.height = value

    def as_collider(self) -> RectangleCollider:
        width = self.width.game_units
        height = self.height.game_units
        x = self.position.game_x - width // 2
        z = self.position.game_z - height // 2
        return RectangleCollider(x, z, width, height, self.unknown)

    @property
    def is_2d(self) -> bool:
        return True

    @property
    def can_resize(self) -> bool:
        return True

    @property
    def vertices(self) -> list[Vec3]:
        center_width = abs(self.width.panda_units / 2)
        center_height = abs(self.height.panda_units / 2)
        return [Vec3(-center_width, -center_height, 0), Vec3(center_width, -center_height, 0),
                Vec3(center_width, center_height, 0), Vec3(-center_width, center_height, 0)]

    def get_pos_cursor_type(self, camera: NodePath, entry: CollisionEntry) -> Cursor | None:
        center_width = abs(self.width.panda_units / 2)
        center_height = abs(self.height.panda_units / 2)
        relative_point = entry.getSurfacePoint(self.node_path)
        if (abs(relative_point[0]) <= center_width * CENTER_AREA
                and abs(relative_point[1]) <= center_height * CENTER_AREA):
            return Cursor.CENTER

        corners = [Vec3(-center_width, -center_height, 0), Vec3(center_width, -center_height, 0),
                   Vec3(center_width, center_height, 0), Vec3(-center_width, center_height, 0)]
        angle = self.get_cursor_angle(camera, entry, corners)
        return Cursor.from_angle(angle)

    def start_resize(self, entry: CollisionEntry):
        self.resize_vertices, self.resize_offset = self.get_edge(entry, self.vertices)

    def resize(self, point: Point3):
        corners = self.vertices

        game_point = Point()
        game_point.panda_x = point[0]
        game_point.panda_y = point[1]
        line = Line2d(Point(), game_point)  # relative center is at (0, 0)
        final_point = line.get_point_at_distance(line.panda_len + self.resize_offset)
        new_vert = final_point.panda_point

        if len(self.resize_vertices) == 1:
            # we're moving a corner, so we're resizing in two dimensions
            index = self.resize_vertices[0]
            old_vert = corners[index]
            for neighbor in [corners[(index - 1) % 4], corners[(index + 1) % 4]]:
                if neighbor[0] == old_vert[0]:
                    neighbor[0] = new_vert[0]
                else:
                    neighbor[1] = new_vert[1]
            corners[index] = new_vert
        else:
            # we're moving an edge, so we're resizing in one dimension
            index1, index2 = self.resize_vertices
            vert1 = corners[index1]
            vert2 = corners[index2]
            # this works because the rectangle's sides are always straight in its own reference frame
            if vert1[0] == vert2[0]:
                vert1[0] = new_vert[0]
                vert2[0] = new_vert[0]
            else:
                vert1[1] = new_vert[1]
                vert2[1] = new_vert[1]

        game_corners = []
        for corner in corners:
            p = Point()
            p.panda_point = corner
            game_corners.append(p)

        min_x = min(p.game_x for p in game_corners)
        max_x = max(p.game_x for p in game_corners)
        min_z = min(p.game_z for p in game_corners)
        max_z = max(p.game_z for p in game_corners)

        new_width = Dimension(max_x - min_x, True)
        width_diff = new_width - self.width
        if final_point.game_x < 0:
            width_diff = -width_diff
        new_height = Dimension(max_z - min_z)
        height_diff = new_height - self.height
        if final_point.game_z < 0:
            height_diff = -height_diff
        self.node_path.setPos(self.node_path, Vec3(width_diff.panda_units / 2, height_diff.panda_units / 2, 0))
        self.position.panda_point = self.node_path.getPos()

        half_x = new_width.panda_units / 2
        half_z = new_height.panda_units / 2
        vdata = self.original_model.node().modifyGeom(0).modifyVertexData()
        util.update_quad(vdata, (-half_x, -half_z), (half_x, -half_z), (half_x, half_z), (-half_x, half_z))
        self.width = new_width
        self.height = new_height


class WallColliderObject(RectangleColliderObject):
    def __init__(self, name: str, bounds: RectangleCollider):
        super().__init__(name, bounds)
        self.color = (0.75, 0., 0., 0.9)
        self.is_wall = True


class TriangleColliderObject(RoomObject):
    def __init__(self, name: str, bounds: TriangleCollider):
        p1 = Point(bounds.x1, 0, bounds.z1)
        p2 = Point(bounds.x2, 0, bounds.z2)
        p3 = Point(bounds.x3, 0, bounds.z3)
        self.triangle = Triangle2d(p1, p2, p3)
        centroid = self.triangle.centroid
        self.relative = Triangle2d(p1 - centroid, p2 - centroid, p3 - centroid)
        super().__init__(name, centroid, 0)
        self.color = COLLIDER_COLOR
        self.resize_vertices = []
        self.resize_offset = 0

    @property
    def p1(self) -> Point:
        return self.triangle.p1

    @p1.setter
    def p1(self, value: Point):
        self.triangle.p1 = value

    @property
    def p2(self) -> Point:
        return self.triangle.p2

    @p2.setter
    def p2(self, value: Point):
        self.triangle.p2 = value

    @property
    def p3(self) -> Point:
        return self.triangle.p3

    @p3.setter
    def p3(self, value: Point):
        self.triangle.p3 = value

    @property
    def vertices(self) -> list[Point3]:
        return [
            self.relative.p1.panda_point,
            self.relative.p2.panda_point,
            self.relative.p3.panda_point,
        ]

    def get_model(self) -> NodePath:
        geom = util.make_triangle(
            (self.p1.panda_x - self.position.panda_x, self.p1.panda_y - self.position.panda_y),
            (self.p2.panda_x - self.position.panda_x, self.p2.panda_y - self.position.panda_y),
            (self.p3.panda_x - self.position.panda_x, self.p3.panda_y - self.position.panda_y),
            False,
        )

        node = GeomNode('triangle_collider_triangle')
        node.addGeom(geom)
        return NodePath(node)

    def add_to_scene(self, scene: NodePath):
        super().add_to_scene(scene)
        self.node_path.setTwoSided(True)

    def recalculate_center(self):
        centroid = self.triangle.centroid
        self.position.x = centroid.x
        self.position.y = centroid.y

    def as_collider(self) -> TriangleCollider:
        return TriangleCollider(self.triangle.p1.game_x, self.triangle.p1.game_z,
                                self.triangle.p2.game_x, self.triangle.p2.game_z,
                                self.triangle.p3.game_x, self.triangle.p3.game_z,
                                )

    @property
    def is_2d(self) -> bool:
        return True

    @property
    def can_resize(self) -> bool:
        return True

    @property
    def can_rotate(self) -> bool:
        return True

    def set_relative(self, p1: Point3, p2: Point3, p3: Point3):
        vdata = self.original_model.node().modifyGeom(0).modifyVertexData()
        util.update_triangle(vdata, p1, p2, p3)
        self.relative.p1.panda_point = p1
        self.relative.p2.panda_point = p2
        self.relative.p3.panda_point = p3
        panda_position = self.position.panda_point
        self.p1.panda_point = p1 + panda_position
        self.p2.panda_point = p2 + panda_position
        self.p3.panda_point = p3 + panda_position

    def move(self, direction: Vec3):
        super().move(direction)
        pos = self.node_path.getPos()
        self.p1.panda_point = self.relative.p1.panda_point + pos
        self.p2.panda_point = self.relative.p2.panda_point + pos
        self.p3.panda_point = self.relative.p3.panda_point + pos

    def rotate(self, angle: float):
        rotate_mat = Mat3.rotateMat(angle)
        p1 = rotate_mat.xform(self.relative.p1.panda_point)
        p2 = rotate_mat.xform(self.relative.p2.panda_point)
        p3 = rotate_mat.xform(self.relative.p3.panda_point)
        self.set_relative(p1, p2, p3)

    def get_pos_cursor_type(self, camera: NodePath, entry: CollisionEntry) -> Cursor | None:
        # FIXME: this doesn't always scale correctly and can result in the center cursor showing when it shouldn't
        scale_mat = Mat3.scaleMat(Vec3(CENTER_AREA, CENTER_AREA, CENTER_AREA))
        p1_scaled = scale_mat.xform(self.relative.p1.panda_point)
        p2_scaled = scale_mat.xform(self.relative.p2.panda_point)
        p3_scaled = scale_mat.xform(self.relative.p3.panda_point)

        center_p1 = Point()
        center_p1.panda_point = p1_scaled

        center_p2 = Point()
        center_p2.panda_point = p2_scaled

        center_p3 = Point()
        center_p3.panda_point = p3_scaled

        center_tri = Triangle2d(center_p1, center_p2, center_p3)

        rel_intersection = entry.getSurfacePoint(self.node_path)
        rel_point = Point()
        rel_point.panda_x = rel_intersection[0]
        rel_point.panda_y = rel_intersection[1]

        if center_tri.is_point_within(rel_point):
            return Cursor.CENTER

        vertices = [Vec3(center_p1.panda_x, center_p1.panda_y, 0), Vec3(center_p2.panda_x, center_p2.panda_y, 0),
                    Vec3(center_p3.panda_x, center_p3.panda_y, 0)]
        angle = self.get_cursor_angle(camera, entry, vertices)
        return Cursor.from_angle(angle)

    def start_resize(self, entry: CollisionEntry):
        self.resize_vertices, self.resize_offset = self.get_edge(entry, self.vertices)

    def resize(self, point: Point3):
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

        self.set_relative(corners[0], corners[1], corners[2])


class CircleColliderObject(RoomObject):
    texture_cache = {}

    def __init__(self, name: str, bounds: CircleCollider):
        super().__init__(name, Point(bounds.x, 0, bounds.z), 0)
        self.radius = Dimension(bounds.radius)
        self.color = COLLIDER_COLOR
        self.resize_offset = 0

    @classmethod
    def create_texture(cls, width: int, height: int, color: tuple[float, float, float, float]) -> Texture:
        key = (width, height, *color)
        if texture := cls.texture_cache.get(key):
            return texture

        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse([(0, 0), (width - 1, height - 1)], tuple(int(c * 255) for c in color))

        texture = util.create_texture_from_image(image)
        # prevents artifacts around the edge of the circle
        texture.setMagfilter(SamplerState.FT_nearest)
        texture.setMinfilter(SamplerState.FT_nearest)
        cls.texture_cache[key] = texture
        return texture

    def add_to_scene(self, scene: NodePath):
        super().add_to_scene(scene)
        self.node_path.setTwoSided(True)

    def get_model(self) -> NodePath:
        radius = self.radius.panda_units
        geom = util.make_quad((-radius, -radius), (radius, -radius), (radius, radius), (-radius, radius), True, False)
        node = GeomNode('circle_collider_quad')
        node.addGeom(geom)
        return NodePath(node)

    def get_texture(self) -> Texture | None:
        return self.create_texture(500, 500, self.color)

    def as_collider(self) -> CircleCollider:
        return CircleCollider(self.position.game_x, self.position.game_z, self.radius.game_units)

    @property
    def is_2d(self) -> bool:
        return True

    @property
    def can_resize(self) -> bool:
        return True

    def get_pos_cursor_type(self, camera: NodePath, entry: CollisionEntry) -> Cursor | None:
        # since we use a circle texture on a square mesh, we need to make sure the point is actually on the circle
        camera_center = self.node_path.getPos(camera)
        camera_intersection = entry.getSurfacePoint(camera)
        relative_point = camera_center - camera_intersection
        distance = relative_point.length()
        radius = self.radius.panda_units
        if distance > radius:
            return None
        if distance < radius * CENTER_AREA:
            return Cursor.CENTER

        lens = camera.node().getLens()
        screen_center = Point2()
        lens.project(camera_center, screen_center)
        screen_intersection = Point2()
        lens.project(camera_intersection, screen_intersection)
        screen_relative = screen_center - screen_intersection
        angle = math.degrees(math.atan2(screen_relative[1], screen_relative[0])) % 360
        return Cursor.from_angle(angle)

    def start_resize(self, entry: CollisionEntry):
        self.resize_offset = self.radius.panda_units - entry.getSurfacePoint(self.node_path).length()

    def resize(self, point: Point3):
        new_radius = Dimension()
        new_radius.panda_units = point.length() + self.resize_offset
        self.radius = new_radius
        radius = self.radius.panda_units
        # I tried using scaling instead of changing the vertex data because I thought it might be easier and more
        # efficient, but for some reason, the mouse ray stopped detecting collisions on objects after I scaled them
        vdata = self.original_model.node().modifyGeom(0).modifyVertexData()
        util.update_quad(vdata, (-radius, -radius), (radius, -radius), (radius, radius), (-radius, radius), True)
