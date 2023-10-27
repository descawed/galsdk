from panda3d.core import GeomNode, NodePath, SamplerState, Texture
from PIL import Image, ImageDraw

from galsdk import util
from galsdk.coords import Dimension, Point, Triangle2d
from galsdk.module import CircleCollider, RectangleCollider, TriangleCollider
from galsdk.room.object import RoomObject


COLLIDER_COLOR = (0., 1., 0., 0.5)


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
