from abc import ABC, abstractmethod

from panda3d.core import Geom, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter


class RoomObject(ABC):
    def __init__(self, x: float, y: float, z: float, angle: float):
        self.x = x
        self.y = y
        self.z = z
        self.angle = angle

    @staticmethod
    def _make_triangle(p1: tuple[float, float], p2: tuple[float, float], p3: tuple[float, float],
                       color: tuple[int, int, int, int]) -> Geom:
        vdata = GeomVertexData('', GeomVertexFormat.getV3c4(), Geom.UHStatic)
        vdata.setNumRows(3)

        vertex = GeomVertexWriter(vdata, 'vertex')
        color_writer = GeomVertexWriter(vdata, 'color')
        vertex.addData3(p1[0], p1[1], 0)
        vertex.addData3(p2[0], p2[1], 0)
        vertex.addData3(p3[0], p3[1], 0)

        for _ in range(3):
            color_writer.addData4(*color)

        primitive = GeomTriangles(Geom.UHStatic)
        primitive.addVertices(0, 1, 2)
        primitive.closePrimitive()

        geom = Geom(vdata)
        geom.addPrimitive(primitive)
        return geom

    @staticmethod
    def _make_quad(p1: tuple[float, float], p2: tuple[float, float], p3: tuple[float, float],
                   p4: tuple[float, float], color: tuple[int, int, int, int] = None) -> Geom:
        vertex_format = GeomVertexFormat.getV3t2() if color is None else GeomVertexFormat.getV3c4()
        vdata = GeomVertexData('', vertex_format, Geom.UHStatic)
        vdata.setNumRows(4)

        vertex = GeomVertexWriter(vdata, 'vertex')
        vertex.addData3(p1[0], p1[1], 0)
        vertex.addData3(p2[0], p2[1], 0)
        vertex.addData3(p3[0], p3[1], 0)
        vertex.addData3(p4[0], p4[1], 0)

        if color is not None:
            color_writer = GeomVertexWriter(vdata, 'color')
            for _ in range(4):
                color_writer.addData4(*color)
        else:
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
