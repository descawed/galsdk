import math
from abc import ABC, abstractmethod

from panda3d.core import CollisionEntry, NodePath, PandaNode, Point2, Point3, Texture, Vec3

from galsdk.coords import Point
from galsdk.ui.viewport import Cursor


class RoomObject(ABC):
    node_path: NodePath | None

    def __init__(self, name: str, position: Point, angle: float):
        self.name = name
        self.position = position
        self.angle = angle
        self.node_path = NodePath(PandaNode(f'{name}_object'))
        self.node_path.setTag('object_name', name)
        self.original_model = None
        self.model_node = None
        self.scene = None
        self.color = (0., 0., 0., 0.)

    def add_to_scene(self, scene: NodePath):
        self.scene = scene
        self.node_path.reparentTo(scene)
        self.update()

    def remove_from_scene(self):
        if self.node_path:
            self.node_path.removeNode()
            self.node_path = None
            self.scene = None

    def update_model(self):
        if model := self.get_model():
            if self.original_model is not model:
                self.original_model = model
                if self.model_node:
                    self.model_node.removeNode()
                # because we frequently reuse the same model (i.e. same NodePath) for different instances of the same
                # character, we need to make separate instances of the model for each RoomObject, otherwise we'll have
                # problems when a room includes more than one of the same type of NPC
                self.model_node = self.original_model.instanceUnderNode(self.node_path, f'{self.name}_instance')

    def update_texture(self):
        if self.model_node:
            if texture := self.get_texture():
                self.model_node.setTexture(texture, 1)
            else:
                self.model_node.setColor(*self.color)

    def update_position(self):
        self.node_path.setPos(self.position.panda_x, self.position.panda_y, self.position.panda_z)
        self.node_path.setH(self.angle)

    def set_color(self, color: tuple[float, float, float, float]):
        self.color = color
        self.update_texture()

    def update(self):
        self.update_model()
        self.update_texture()
        self.update_position()

    def show(self):
        self.node_path.show()

    def hide(self):
        self.node_path.hide()

    def move_to(self, point: Point3):
        self.position.panda_x = point[0]
        self.position.panda_y = point[1]
        self.position.panda_z = point[2]
        self.update_position()

    def rotate(self, angle: float):
        self.angle = (self.angle + angle) % 360
        self.update_position()

    @abstractmethod
    def get_model(self) -> NodePath | None:
        pass

    def get_texture(self) -> Texture | None:
        return None

    @property
    def can_resize(self) -> bool:
        return False

    @property
    def is_2d(self) -> bool:
        return False

    @property
    def can_rotate(self) -> bool:
        return False

    def get_pos_cursor_type(self, camera: NodePath, entry: CollisionEntry) -> Cursor | None:
        return Cursor.CENTER

    def get_cursor_angle(self, camera: NodePath, entry: CollisionEntry, vertices: list[Vec3]) -> float:
        lens = camera.node().getLens()
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
        edges = [
            (screen_vertices[i], screen_vertices[i + 1 if i + 1 < len(screen_vertices) else 0])
            for i in range(len(screen_vertices))
        ]
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
                c = m * edge[0][0] - edge[0][1]

            distance = abs(a * screen_intersection[0] + b * screen_intersection[1] + c) / math.sqrt(a ** 2 + b ** 2)
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
        return (math.degrees(math.atan2(point2[1] - point1[1], point2[0] - point1[0])) - offset) % 360
