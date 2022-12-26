from abc import ABC, abstractmethod

from panda3d.core import Geom, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter, Texture


class RoomObject(ABC):
    def __init__(self, x: float, y: float, z: float, angle: float):
        self.x = x
        self.y = y
        self.z = z
        self.angle = angle

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

    @abstractmethod
    def get_model(self) -> Geom:
        pass

    def get_texture(self) -> Texture | None:
        return None
