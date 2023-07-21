from direct.showbase.Loader import Loader
from panda3d.core import NodePath

from galsdk.coords import Point
from galsdk.module import Camera, Background
from galsdk.room.object import RoomObject


class CameraObject(RoomObject):
    def __init__(self, name: str, camera: Camera, backgrounds: list[Background], loader: Loader):
        super().__init__(name, Point(camera.x, camera.y, camera.z), 0)
        self.backgrounds = backgrounds
        self.target = Point(camera.target_x, camera.target_y, camera.target_z)
        self.orientation = camera.orientation
        self.unknown = camera.unknown
        self.fov = camera.vertical_fov / 10
        self.scale = camera.scale
        self.loader = loader
        self.model = loader.loadModel('movie_camera.egg')
        self.model.setScale(2)
        self.model.setHpr(90, 90, 0)
        self.model.reparentTo(self.node_path)
        self.color = (0.5, 0.5, 0.5, 0.9)

    def remove_from_scene(self):
        self.node_path.detachNode()

    def update_position(self):
        super().update_position()
        self.node_path.lookAt(self.target.panda_x, self.target.panda_y, self.target.panda_z)

    def get_model(self) -> NodePath | None:
        return None

    def as_camera(self) -> Camera:
        return Camera(self.orientation, int(self.fov * 10), self.scale, self.position.game_x, self.position.game_y,
                      self.position.game_z, self.target.game_x, self.target.game_y, self.target.game_z, self.unknown)
