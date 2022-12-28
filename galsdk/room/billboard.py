from panda3d.core import Geom, NodePath, Texture

from galsdk.coords import Point
from galsdk.room.object import RoomObject
from psx.tim import Tim, Transparency


class BillboardObject(RoomObject):
    SIZE = 50

    def __init__(self, name: str, image: Tim):
        super().__init__(name, Point(), 0)
        self.image = image
        width_to_height_ratio = self.image.width / self.image.height
        self.width = self.SIZE * width_to_height_ratio
        self.height = self.SIZE

    def get_model(self) -> Geom | None:
        return self._make_quad(
            (-self.width, -self.height),
            (self.width, -self.height),
            (self.width, self.height),
            (-self.width, self.height),
            True)

    def get_texture(self) -> Texture | None:
        return self._create_texture_from_image(self.image.to_image(0, Transparency.NONE))

    def add_to_scene(self, scene: NodePath):
        super().add_to_scene(scene)
        # I think this is the "right" way to do a 2D background, but
        # self.node_path.setBillboardPointEye(-5, fixed_depth=True)
        self.node_path.setDepthWrite(False)
        self.node_path.setDepthTest(False)
        self.node_path.setTwoSided(True)