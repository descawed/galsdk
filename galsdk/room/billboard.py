from panda3d.core import BitMask32, GeomNode, NodePath, Texture
from PIL.Image import Image

from galsdk import graphics
from galsdk.coords import Point
from galsdk.room.object import RoomObject


class BillboardObject(RoomObject):
    SIZE = 50

    def __init__(self, name: str, image: Image, pickable: bool = False):
        super().__init__(name, Point(), 0)
        self.image = image
        width_to_height_ratio = self.image.width / self.image.height
        self.width = self.SIZE * width_to_height_ratio
        self.height = self.SIZE
        self.pickable = pickable

    def get_model(self) -> NodePath:
        geom = graphics.make_quad(
            (-self.width, -self.height),
            (self.width, -self.height),
            (self.width, self.height),
            (-self.width, self.height),
            True)

        node = GeomNode('billboard_quad')
        node.addGeom(geom)
        return NodePath(node)

    def get_texture(self) -> Texture | None:
        return graphics.create_texture_from_image(self.image)

    def add_to_scene(self, scene: NodePath):
        super().add_to_scene(scene)
        # I think this is the "right" way to do a 2D background, but when I tried this the background disappeared
        # self.node_path.setBillboardPointEye(-5, fixed_depth=True)
        self.node_path.setDepthWrite(False)
        self.node_path.setDepthTest(False)
        if not self.pickable:
            self.node_path.setCollideMask(BitMask32(0))
