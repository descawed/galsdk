from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Callable

from panda3d.core import CollisionEntry, NodePath, PandaNode, Point2, Point3, Texture, Vec3

from galsdk.coords import Line2d, Point
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
        self.listeners = set()

    def on_transform(self, callback: Callable[[RoomObject], None]):
        self.listeners.add(callback)

    def remove_on_transform(self, callback: Callable[[RoomObject], None]):
        self.listeners.remove(callback)

    def notify_transform(self):
        for listener in self.listeners:
            listener(self)

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

    def move(self, direction: Vec3):
        self.node_path.setPos(self.node_path, direction)
        pos = self.node_path.getPos()
        self.position.panda_point = pos
        self.notify_transform()

    def move_to(self, point: Point3):
        self.position.panda_point = point
        self.update_position()
        self.notify_transform()

    def rotate(self, angle: float):
        self.angle = (self.angle + angle) % 360
        self.update_position()
        self.notify_transform()

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

    def start_resize(self, entry: CollisionEntry):
        pass

    def resize(self, point: Point3):
        pass

    def get_pos_cursor_type(self, camera: NodePath, entry: CollisionEntry) -> Cursor | None:
        return Cursor.CENTER

    def get_edge(self, entry: CollisionEntry, vertices: list[Vec3]) -> tuple[list[int], float]:
        intersection = entry.getSurfacePoint(self.node_path)

        num_vertices = len(vertices)
        edges = [(vertices[i], vertices[(i + 1) % num_vertices]) for i in range(num_vertices)]
        closest_edge = 0
        min_distance = None
        for i, edge in enumerate(edges):
            # Ax + By + C = 0
            if edge[0][0] == edge[1][0]:
                a = 1
                b = 0
                c = -edge[0][0]
            else:
                m = (edge[0][1] - edge[1][1]) / (edge[0][0] - edge[1][0])
                a = -m
                b = 1
                c = m * edge[0][0] - edge[0][1]

            distance = abs(a * intersection[0] + b * intersection[1] + c) / math.sqrt(a ** 2 + b ** 2)
            if min_distance is None or distance < min_distance:
                min_distance = distance
                closest_edge = i

        edge2_index = (closest_edge + 1) % num_vertices
        edge1, edge2 = edges[closest_edge]
        edge1_distance = (edge1 - intersection).length()
        edge2_distance = (edge2 - intersection).length()
        # we divide each edge into quarters. if we're in the quarter closest to a corner, we attach to that corner.
        # otherwise, we attach to the edge.
        if edge1_distance / edge2_distance >= 3:
            return [edge2_index], edge2_distance
        elif edge2_distance / edge1_distance >= 3:
            return [closest_edge], edge1_distance
        else:
            return [closest_edge, edge2_index], min_distance

    def get_cursor_angle(self, camera: NodePath, entry: CollisionEntry, vertices: list[Vec3]) -> float:
        lens = camera.node().getLens()

        screen_center = Point2()
        lens.project(self.node_path.getPos(camera), screen_center)

        edge_points = self.get_edge(entry, vertices)[0]
        screen_vertices = []
        for vertex in vertices:
            screen_vertex = Point2()
            lens.project(camera.getRelativePoint(self.node_path, vertex), screen_vertex)
            screen_vertices.append(screen_vertex)
        if len(edge_points) < 2:
            # need to find the angle bisector
            i = edge_points[0]
            vertex = screen_vertices[i]
            num_vertices = len(screen_vertices)
            neighbor1 = screen_vertices[(i - 1) % num_vertices]
            neighbor2 = screen_vertices[(i + 1) % num_vertices]
            p = Point()
            p.panda_x = vertex[0]
            p.panda_y = vertex[1]
            q = Point()
            q.panda_x = neighbor1[0]
            q.panda_y = neighbor1[1]
            r = Point()
            r.panda_x = neighbor2[0]
            r.panda_y = neighbor2[1]

            # https://www.cuemath.com/geometry/angle-bisector/#e
            pq = Line2d(p, q)
            pr = Line2d(p, r)
            qr = Line2d(q, r)
            c = qr.panda_len
            y = c / (pq.panda_len / pr.panda_len + 1)
            s = qr.get_point_at_distance(c - y)
            return math.degrees(math.atan2(p.panda_y - s.panda_y, p.panda_x - s.panda_x)) % 360
        else:
            point1 = screen_vertices[edge_points[0]]
            point2 = screen_vertices[edge_points[1]]
            # rotate 90 degrees to get the angle through the edge instead of the angle of the edge itself
            return (math.degrees(math.atan2(point2[1] - point1[1], point2[0] - point1[0])) - 90) % 360
