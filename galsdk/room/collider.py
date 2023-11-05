import math

from panda3d.core import CollisionEntry, GeomNode, NodePath, Point2, SamplerState, Texture, Vec3
from PIL import Image, ImageDraw

from galsdk import util
from galsdk.coords import Dimension, Point, Triangle2d
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
    def z_pos(self) -> Dimension:
        return self.position.y - self.height // 2

    @z_pos.setter
    def z_pos(self, value: Dimension):
        self.position.y = value + self.height // 2

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

    def get_pos_cursor_type(self, camera: NodePath, entry: CollisionEntry) -> Cursor | None:
        center_width = abs(self.width.panda_units / 2)
        center_height = abs(self.height.panda_units / 2)
        relative_point = entry.getSurfacePoint(self.node_path)
        if (abs(relative_point[0]) <= center_width * CENTER_AREA
                and abs(relative_point[1]) <= center_height * CENTER_AREA):
            return Cursor.CENTER

        lens = camera.node().getLens()
        corners = [Vec3(-center_width, -center_height, 0), Vec3(center_width, -center_height, 0),
                   Vec3(center_width, center_height, 0), Vec3(-center_width, center_height, 0)]
        screen_corners = []
        for corner in corners:
            screen_corner = Point2()
            lens.project(camera.getRelativePoint(self.node_path, corner), screen_corner)
            screen_corners.append(screen_corner)

        screen_intersection = Point2()
        lens.project(entry.getSurfacePoint(camera), screen_intersection)
        screen_center = Point2()
        lens.project(self.node_path.getPos(camera), screen_center)
        # get the diagonals of the rectangle to determine which side we're closest to
        diagonal1 = sorted((screen_corners[0], screen_corners[2]), key=lambda p: (p[1], p[0]))
        diagonal2 = sorted((screen_corners[3], screen_corners[1]), key=lambda p: (p[1], p[0]))
        edges = []
        for diag in [diagonal1, diagonal2]:
            if diag[0][0] == diag[1][0]:
                # vertical line
                edges.append(abs(diag[0][0] - screen_intersection[0]) >= abs(diag[1][0] - screen_intersection[0]))
            else:
                m = (diag[0][1] - diag[1][1]) / (diag[0][0] - diag[1][0])
                y = m*(screen_intersection[0] - diag[0][0]) + diag[0][1]
                edges.append(screen_intersection[1] > y)
        edge1 = diagonal2[edges[0]]
        edge2 = diagonal1[edges[1]]

        edge1_distance = (edge1 - screen_intersection).length()
        edge2_distance = (edge2 - screen_intersection).length()
        # we divide each edge into quarters. if we're in the quarter closest to a corner, we attach to that corner.
        # otherwise, we attach to the edge.
        if edge1_distance / edge2_distance >= 3:
            point1 = edge2
            point2 = screen_center
            offset = 0
        elif edge2_distance / edge1_distance >= 3:
            point1 = edge1
            point2 = screen_center
            offset = 0
        else:
            point1 = edge1
            point2 = edge2
            # rotate 90 degrees to get the angle through the edge instead of the angle of the edge itself
            offset = 90
        angle = (math.degrees(math.atan2(point2[1] - point1[1], point2[0] - point1[0])) - offset) % 360
        return Cursor.from_angle(angle)


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
        super().__init__(name, centroid, 0)
        self.color = COLLIDER_COLOR

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

    def get_model(self) -> NodePath:
        geom = util.make_triangle(
            (self.p1.panda_x - self.position.panda_x, self.p1.panda_y - self.position.panda_y),
            (self.p2.panda_x - self.position.panda_x, self.p2.panda_y - self.position.panda_y),
            (self.p3.panda_x - self.position.panda_x, self.p3.panda_y - self.position.panda_y),
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

        center_tri = Triangle2d(center_p1, center_p2, center_p3)

        rel_intersection = entry.getSurfacePoint(self.node_path)
        rel_point = Point()
        rel_point.panda_x = rel_intersection[0]
        rel_point.panda_y = rel_intersection[1]

        if center_tri.is_point_within(rel_point):
            return Cursor.CENTER

        lens = camera.node().getLens()
        vertices = [Vec3(center_p1.panda_x, center_p1.panda_y, 0), Vec3(center_p2.panda_x, center_p2.panda_y, 0),
                    Vec3(center_p3.panda_x, center_p3.panda_y, 0)]
        screen_vertices = []
        for vertex in vertices:
            screen_vertex = Point2()
            lens.project(camera.getRelativePoint(self.node_path, vertex), screen_vertex)
            screen_vertices.append(screen_vertex)

        screen_intersection = Point2()
        lens.project(entry.getSurfacePoint(camera), screen_intersection)
        screen_center = Point2()
        lens.project(self.node_path.getPos(camera), screen_center)

        # find the closest edge
        edges = [(screen_vertices[0], screen_vertices[1]), (screen_vertices[1], screen_vertices[2]),
                 (screen_vertices[2], screen_vertices[0])]
        closest_edge = 0
        min_distance = None
        for i, edge in enumerate(edges):
            if edge[0][0] == edge[1][0]:
                a = 1
                b = 0
                c = -edge[0][0]
            else:
                m = (edge[0][1] - edge[1][1]) / (edge[0][0] - edge[1][0])
                a = -m
                b = 1
                c = m*edge[0][0] - edge[0][1]

            distance = abs(a*screen_intersection[0] + b*screen_intersection[1] + c)/math.sqrt(a**2 + b**2)
            if min_distance is None or distance < min_distance:
                min_distance = distance
                closest_edge = i

        edge1, edge2 = edges[closest_edge]
        edge1_distance = (edge1 - screen_intersection).length()
        edge2_distance = (edge2 - screen_intersection).length()
        # we divide each edge into quarters. if we're in the quarter closest to a corner, we attach to that corner.
        # otherwise, we attach to the edge.
        if edge1_distance / edge2_distance >= 3:
            point1 = edge2
            point2 = screen_center
            offset = 0
        elif edge2_distance / edge1_distance >= 3:
            point1 = edge1
            point2 = screen_center
            offset = 0
        else:
            point1 = edge1
            point2 = edge2
            # rotate 90 degrees to get the angle through the edge instead of the angle of the edge itself
            offset = 90
        angle = (math.degrees(math.atan2(point2[1] - point1[1], point2[0] - point1[0])) - offset) % 360
        return Cursor.from_angle(angle)


class CircleColliderObject(RoomObject):
    texture_cache = {}

    def __init__(self, name: str, bounds: CircleCollider):
        super().__init__(name, Point(bounds.x, 0, bounds.z), 0)
        self.radius = Dimension(bounds.radius)
        self.color = COLLIDER_COLOR

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
        geom = util.make_quad((-radius, -radius), (radius, -radius), (radius, radius), (-radius, radius), True)
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
