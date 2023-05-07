import io
from abc import ABC, abstractmethod

from panda3d.core import Geom, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter, NodePath,\
    PandaNode, Texture, StringStream, PNMImage
from PIL import Image

from galsdk.coords import Point


class RoomObject(ABC):
    node_path: NodePath | None

    def __init__(self, name: str, position: Point, angle: float):
        self.name = name
        self.position = position
        self.angle = angle
        self.node_path = NodePath(PandaNode(f'{name}_object'))
        self.original_model = None
        self.model_node = None
        self.scene = None
        self.color = (0., 0., 0., 0.)

    @staticmethod
    def _make_triangle(p1: tuple[float, float], p2: tuple[float, float], p3: tuple[float, float]) -> Geom:
        vdata = GeomVertexData('', GeomVertexFormat.getV3(), Geom.UHStatic)
        vdata.setNumRows(3)

        vertex = GeomVertexWriter(vdata, 'vertex')
        vertex.addData3(p1[0], p1[1], 0)
        vertex.addData3(p2[0], p2[1], 0)
        vertex.addData3(p3[0], p3[1], 0)

        primitive = GeomTriangles(Geom.UHStatic)
        primitive.addVertices(0, 1, 2)
        primitive.closePrimitive()

        geom = Geom(vdata)
        geom.addPrimitive(primitive)
        return geom

    @staticmethod
    def _make_quad(p1: tuple[float, float], p2: tuple[float, float], p3: tuple[float, float],
                   p4: tuple[float, float], use_texture: bool = False) -> Geom:
        vertex_format = GeomVertexFormat.getV3t2() if use_texture else GeomVertexFormat.getV3()
        vdata = GeomVertexData('', vertex_format, Geom.UHStatic)
        vdata.setNumRows(4)

        vertex = GeomVertexWriter(vdata, 'vertex')
        vertex.addData3(p1[0], p1[1], 0)
        vertex.addData3(p2[0], p2[1], 0)
        vertex.addData3(p3[0], p3[1], 0)
        vertex.addData3(p4[0], p4[1], 0)

        if use_texture:
            texcoord = GeomVertexWriter(vdata, 'texcoord')
            texcoord.addData2(0, 0)
            texcoord.addData2(1, 0)
            texcoord.addData2(1, 1)
            texcoord.addData2(0, 1)

        primitive = GeomTriangles(Geom.UHStatic)
        primitive.addVertices(0, 1, 2)
        primitive.addVertices(2, 3, 0)
        primitive.closePrimitive()

        geom = Geom(vdata)
        geom.addPrimitive(primitive)
        return geom

    @staticmethod
    def _create_texture_from_image(image: Image) -> Texture:
        buffer = io.BytesIO()
        image.save(buffer, format='png')

        panda_image = PNMImage()
        panda_image.read(StringStream(buffer.getvalue()))

        texture = Texture()
        texture.load(panda_image)
        return texture

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

    @abstractmethod
    def get_model(self) -> NodePath | None:
        pass

    def get_texture(self) -> Texture | None:
        return None
