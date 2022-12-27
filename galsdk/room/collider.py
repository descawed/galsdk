import io

from panda3d.core import Geom, NodePath, PNMImage, SamplerState, StringStream, Texture
from PIL import Image, ImageDraw

from galsdk.coords import Dimension, Point
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
        self.color = COLLIDER_COLOR

    def get_model(self) -> Geom:
        half_x = (self.width / 2).panda_units
        half_z = (self.height / 2).panda_units
        return self._make_quad((-half_x, -half_z), (half_x, -half_z), (half_x, half_z), (-half_x, half_z))

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


class WallColliderObject(RectangleColliderObject):
    def __init__(self, name: str, bounds: RectangleCollider):
        super().__init__(name, bounds)
        self.color = (0.75, 0., 0., 1.)


class TriangleColliderObject(RoomObject):
    def __init__(self, name: str, bounds: TriangleCollider):
        self.p1 = Point(bounds.x1, 0, bounds.z1)
        self.p2 = Point(bounds.x2, 0, bounds.z2)
        self.p3 = Point(bounds.x3, 0, bounds.z3)
        centroid = self.find_centroid()
        super().__init__(name, centroid, 0)
        self.color = COLLIDER_COLOR

    def get_model(self) -> Geom:
        return self._make_triangle(
            (self.p1.panda_x - self.position.panda_x, self.p1.panda_y - self.position.panda_y),
            (self.p2.panda_x - self.position.panda_x, self.p2.panda_y - self.position.panda_y),
            (self.p3.panda_x - self.position.panda_x, self.p3.panda_y - self.position.panda_y),
        )

    def add_to_scene(self, scene: NodePath):
        super().add_to_scene(scene)
        self.node_path.setTwoSided(True)

    @staticmethod
    def _find_midpoint(p1: tuple[float, float], p2: tuple[float, float]) -> tuple[float, float]:
        x = p1[0] + (p2[0] - p1[0]) / 2
        y = p1[1] + (p2[1] - p1[1]) / 2
        return x, y
    
    @staticmethod
    def _find_intersection(a1: tuple[float, float], a2: tuple[float, float],
                           b1: tuple[float, float], b2: tuple[float, float]) -> tuple[float, float]:
        try:
            am = (a2[1] - a1[1]) / (a2[0] - a1[0])
        except ZeroDivisionError:
            am = 0.
        ab = a1[1] - am*a1[0]
        try:
            bm = (b2[1] - b1[1]) / (b2[0] - b1[0])
        except ZeroDivisionError:
            bm = 0.
        bb = b1[1] - bm*b1[0]

        try:
            x = (bb - ab)/(am - bm)
        except ZeroDivisionError:
            x = 0.
        y = am*x + ab
        return x, y

    def find_centroid(self) -> Point:
        p1 = (self.p1.panda_x, self.p1.panda_y)
        p2 = (self.p2.panda_x, self.p2.panda_y)
        p3 = (self.p3.panda_x, self.p3.panda_y)

        m12 = self._find_midpoint(p1, p2)
        m23 = self._find_midpoint(p2, p3)

        x, y = self._find_intersection(m12, p3, p1, m23)
        point = Point()
        point.panda_x = x
        point.panda_y = y
        return point

    def recalculate_center(self):
        centroid = self.find_centroid()
        self.position.x = centroid.x
        self.position.y = centroid.y


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

        buffer = io.BytesIO()
        image.save(buffer, format='png')

        panda_image = PNMImage()
        panda_image.read(StringStream(buffer.getvalue()))

        texture = Texture()
        texture.load(panda_image)
        # prevents artifacts around the edge of the circle
        texture.setMagfilter(SamplerState.FT_nearest)
        texture.setMinfilter(SamplerState.FT_nearest)
        cls.texture_cache[key] = texture
        return texture

    def add_to_scene(self, scene: NodePath):
        super().add_to_scene(scene)
        self.node_path.setTwoSided(True)

    def get_model(self) -> Geom:
        radius = self.radius.panda_units
        return self._make_quad((-radius, -radius), (radius, -radius), (radius, radius), (-radius, radius), True)

    def get_texture(self) -> Texture | None:
        return self.create_texture(500, 500, self.color)
