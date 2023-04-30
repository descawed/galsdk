import io
from abc import ABC, abstractmethod

from panda3d.core import Geom, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter, NodePath,\
    Texture, StringStream, PNMImage
from PIL import Image

from galsdk.coords import Point


class RoomObject(ABC):
    node_path: NodePath | None

    def __init__(self, name: str, position: Point, angle: float):
        self.name = name
        self.position = position
        self.angle = angle
        self.node_path = None
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
        self.update()

    def remove_from_scene(self):
        if self.node_path:
            self.node_path.detachNode()
            self.node_path = None
            self.scene = None

    def update_model(self):
        if model := self.get_model():
            if self.node_path is not model:
                self.node_path = model
                if self.scene:
                    self.node_path.reparentTo(self.scene)

    def update_texture(self):
        if self.node_path:
            if texture := self.get_texture():
                self.node_path.setTexture(texture, 1)
            else:
                self.node_path.setColor(*self.color)

    def update_position(self):
        if self.node_path:
            self.node_path.setPos(self.position.panda_x, self.position.panda_y, self.position.panda_z)

    def set_color(self, color: tuple[float, float, float, float]):
        self.color = color
        self.update_texture()

    def update(self):
        self.update_model()
        self.update_texture()
        self.update_position()

    @abstractmethod
    def get_model(self) -> NodePath | None:
        pass

    def get_texture(self) -> Texture | None:
        return None
