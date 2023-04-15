from __future__ import annotations

import functools
import io
import struct
from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum, IntEnum, auto
from pathlib import Path
from typing import Any, BinaryIO, Iterable, Self

from panda3d.core import Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter, NodePath,\
    PNMImage, StringStream, Texture
from PIL import Image

from galsdk import util
from galsdk.coords import Dimension, Point
from galsdk.format import FileFormat
from psx.tim import BitsPerPixel, Tim, Transparency


class Origin(Enum):
    DEFAULT = auto()
    TOP = auto()
    BOTTOM = auto()


class Gltf(IntEnum):
    POINTS = 0
    LINES = 1
    LINE_LOOP = 2
    LINE_STRIP = 3
    TRIANGLES = 4
    TRIANGLE_STRIP = 5
    TRIANGLE_FAN = 6
    BYTE = 5120
    UNSIGNED_BYTE = 5121
    SHORT = 5122
    UNSIGNED_SHORT = 5123
    UNSIGNED_INT = 5125
    FLOAT = 5126
    NEAREST = 9728
    LINEAR = 9729
    NEAREST_MIPMAP_NEAREST = 9984
    LINEAR_MIPMAP_NEAREST = 9985
    NEAREST_MIPMAP_LINEAR = 9986
    LINEAR_MIPMAP_LINEAR = 9987
    REPEAT = 10497
    CLAMP_TO_EDGE = 33071
    MIRRORED_REPEAT = 33648
    ARRAY_BUFFER = 34962
    ELEMENT_ARRAY_BUFFER = 34963


class Segment:
    def __init__(self, clut_index: int, triangles: list[tuple[int, int, int]],
                 quads: list[tuple[int, int, int, int]], offset: tuple[int, int, int] = (0, 0, 0),
                 total_offset: tuple[int, int, int] = None, children: list[Segment] = None):
        self.clut_index = clut_index
        self.triangles = triangles
        self.quads = quads
        self.offset = offset
        self.total_offset = total_offset or offset
        self.children = children or []

    def __len__(self) -> int:
        return 1 + sum(len(child) for child in self.children)

    @property
    def all_triangles(self) -> Iterable[tuple[int, int, int]]:
        yield from self.triangles
        for q in self.quads:
            yield q[0], q[1], q[3]
            yield q[3], q[2], q[0]

    def flatten(self, new_attributes: dict[tuple[int, int, int, int, int], int],
                original_attributes: list[tuple[int, int, int, int, int]]) -> list[tuple[int, int, int]]:
        new_tris = []
        for tri in self.all_triangles:
            new_tri = []
            for index in tri:
                x, y, z, u, v = original_attributes[index]
                new_vert = (x + self.total_offset[0], y + self.total_offset[1], z + self.total_offset[2], u, v)
                new_tri.append(new_attributes.setdefault(new_vert, len(new_attributes)))
            new_tris.append(tuple(new_tri))
        for child in self.children:
            child_tris = child.flatten(new_attributes, original_attributes)
            new_tris.extend(child_tris)
        return new_tris

    def add_offset(self, offset: tuple[int, int, int]):
        self.total_offset = (self.total_offset[0] + offset[0], self.total_offset[1] + offset[1],
                             self.total_offset[2] + offset[2])
        for child in self.children:
            child.add_offset(offset)

    def add_child(self, child: Segment) -> Segment:
        self.children.append(child)
        child.add_offset(self.total_offset)
        return child


@dataclass
class Actor:
    name: str
    id: int
    model_index: int = None


RION = Actor('Rion', 0)
LILIA = Actor('Lilia', 1)
LEM = Actor('Lem', 2)
BIRDMAN = Actor('Birdman', 3)
RAINHEART = Actor('Rainheart', 4)
RITA = Actor('Rita', 5)
CAIN = Actor('Cain', 6)
CROVIC = Actor('Crovic', 7)
JOULE = Actor('Joule', 8)
LEM_ROBOT = Actor('Robot Lem', 9)
GUARD_HOSPITAL_SKINNY = Actor('Hospital Guard (skinny)', 10)
GUARD_HOSPITAL_BURLY = Actor('Hospital Guard (burly)', 11)
GUARD_HOSPITAL_GLASSES = Actor('Hospital Guard (sunglasses)', 12)
GUARD_MECH_SUIT = Actor('Mech Suit Guard', 13)
GUARD_HAZARD_SUIT = Actor('Hazard Suit Guard', 14)
SNIPER = Actor('Sniper', 15)
DOCTOR_BROWN_HAIR = Actor('Doctor (brown hair)', 16)
DOCTOR_BLONDE = Actor('Doctor (blonde)', 17)
DOCTOR_BALD = Actor('Doctor (bald)', 18)
RABBIT_KNIFE = Actor('Rabbit (knife)', 19)
RABBIT_TRENCH_COAT = Actor('Rabbit (trench coat)', 20)
ARABESQUE_BIPED = Actor('Arabesque (biped)', 21)
HOTEL_KNOCK_GUY = Actor('Hotel knock guy', 22)
DANCER = Actor('Dancer', 23)
HOTEL_RECEPTIONIST = Actor('Hotel Receptionist', 24)
HOTEL_GUN_GUY = Actor('Hotel gun guy', 25)
TERRORIST = Actor('Terrorist', 26)
PRIEST = Actor('Priest', 27)
RAINHEART_HAT = Actor('Rainheart (bellhop hat)', 28)
MECH_SUIT_ALT = Actor('Mech Suit (unused?)', 29)
RABBIT_UNARMED = Actor('Rabbit (unarmed)', 30)
ARABESQUE_QUADRUPED = Actor('Arabesque (quadruped)', 31)
HOTEL_KNOCK_GUY_2 = Actor('Hotel knock guy 2', 32)
RAINHEART_SUMMON_ACTOR = Actor('Rainheart summon', 33)
CROVIC_ALT = Actor('Crovic (holding something)', 34)
DOROTHY_EYE = Actor("Dorothy's eye", 35)
RION_PHONE = Actor('Rion (with phone)', 36)
RION_ALT_1 = Actor('Rion (alternate #1)', 37)
RION_ALT_2 = Actor('Rion (alternate #2)', 38)

UNKNOWN_UNUSED = Actor('Unknown (unused)', 39, 20)
DOCTOR_UNUSED_1 = Actor('Doctor (unused #1)', 40, 38)
DOCTOR_UNUSED_2 = Actor('Doctor (unused #2)', 41, 40)
DOCTOR_UNUSED_3 = Actor('Doctor (unused #3)', 42, 42)
RION_UNUSED = Actor('Rion (unused)', 43, 77)

ACTORS = [
    RION, LILIA, LEM, BIRDMAN, RAINHEART, RITA, CAIN, CROVIC, JOULE, LEM_ROBOT, GUARD_HOSPITAL_SKINNY,
    GUARD_HOSPITAL_BURLY, GUARD_HOSPITAL_GLASSES, GUARD_MECH_SUIT, GUARD_HAZARD_SUIT, SNIPER, DOCTOR_BROWN_HAIR,
    DOCTOR_BLONDE, DOCTOR_BALD, RABBIT_KNIFE, RABBIT_TRENCH_COAT, ARABESQUE_BIPED, HOTEL_KNOCK_GUY, DANCER,
    HOTEL_RECEPTIONIST, HOTEL_GUN_GUY, TERRORIST, PRIEST, RAINHEART_HAT, MECH_SUIT_ALT, RABBIT_UNARMED,
    ARABESQUE_QUADRUPED, HOTEL_KNOCK_GUY_2, RAINHEART_SUMMON_ACTOR, CROVIC_ALT, DOROTHY_EYE, RION_PHONE, RION_ALT_1,
    RION_ALT_2, UNKNOWN_UNUSED, DOCTOR_UNUSED_1, DOCTOR_UNUSED_2, DOCTOR_UNUSED_3, RION_UNUSED,
]

CLUT_WIDTH = 16
BLOCK_WIDTH = 64
TEXTURE_WIDTH = 0x100
TEXTURE_HEIGHT = 0x100
VERT_SIZE = 3 * 4
UV_SIZE = 2 * 4


class Model(FileFormat):
    """A 3D model of a game object"""

    def __init__(self, attributes: list[tuple[int, int, int, int, int]], root_segments: list[Segment],
                 texture: Tim, use_transparency: bool = False):
        self.attributes = attributes
        self.root_segments = root_segments
        self.texture = texture
        self.use_transparency = use_transparency

    @property
    @abstractmethod
    def suggested_extension(self) -> str:
        pass

    @functools.cache
    def get_panda3d_model(self, origin: Origin = Origin.DEFAULT) -> Geom:
        triangles = self._all_tris

        # associate all the UVs with the correct vertices
        vertices: list[tuple[int, int, int, int | None, int | None]] = [
            (x, y, z, None, None) for x, y, z in self.vertices
        ]
        final_tris = [[0, 0, 0] for _ in triangles]
        for i, t in enumerate(triangles):
            for j, vertex in enumerate(t):
                x, y, z, old_u, old_v = vertices[vertex.vertex_index]
                u, v = self.uvs[vertex.uv_index]
                if old_u is not None and (old_u != u or old_v != v):
                    # same vertex, different uv; add a new entry
                    index = len(vertices)
                    vertices.append((x, y, z, u, v))
                else:
                    index = vertex.vertex_index
                    vertices[index] = (x, y, z, u, v)
                final_tris[i][j] = index

        points = [(Point(x, y, z), u, v) for x, y, z, u, v in vertices]
        height_offset = 0
        match origin:
            case Origin.TOP:
                height_offset = max(point[0].panda_z for point in points)
            case Origin.BOTTOM:
                height_offset = min(point[0].panda_z for point in points)

        vdata = GeomVertexData('', GeomVertexFormat.getV3t2(), Geom.UHStatic)
        vdata.setNumRows(len(vertices))

        vertex = GeomVertexWriter(vdata, 'vertex')
        texcoord = GeomVertexWriter(vdata, 'texcoord')
        tex_height = self.texture_height
        for x, y, z, u, v in vertices:
            point = Point(x, y, z)
            vertex.addData3(point.panda_x, point.panda_y, point.panda_z - height_offset)
            texcoord.addData2(u / TEXTURE_WIDTH, (tex_height - v) / tex_height)

        primitive = GeomTriangles(Geom.UHStatic)
        for t in final_tris:
            # the -x when adding the vertex data means we have to reverse the vertices for proper winding order
            primitive.addVertices(t[2], t[1], t[0])
        primitive.closePrimitive()

        geom = Geom(vdata)
        geom.addPrimitive(primitive)
        return geom

    @functools.cache
    def get_panda3d_texture(self) -> Texture:
        image = self.get_texture_image()
        buffer = io.BytesIO()
        image.save(buffer, format='png')

        panda_image = PNMImage()
        panda_image.read(StringStream(buffer.getvalue()))

        texture = Texture()
        texture.load(panda_image)
        return texture

    @property
    def texture_height(self) -> int:
        return TEXTURE_HEIGHT * self.texture.num_palettes

    def _flatten(self) -> tuple[list[tuple[int, int, int]], list[tuple[int, int, int, int, int]]]:
        new_tris = []
        new_attributes = {}
        for segment in self.root_segments:
            new_tris.extend(segment.flatten(new_attributes, self.attributes))
        return new_tris, list(new_attributes)

    @classmethod
    def _gltf_add_segment(cls, gltf: dict[str, Any], root_node: dict[str, str | list[int]],
                          buffer: bytearray, segment: Segment):
        buf_offset = len(buffer)
        index_count = 0
        max_index = 0
        for tri in segment.all_triangles:
            buffer += struct.pack('<3H', tri[0], tri[1], tri[2])
            new_max = max(tri)
            if new_max > max_index:
                max_index = new_max
            index_count += 3
        root_node['children'].append(len(gltf['nodes']))
        node = {
            'mesh': len(gltf['meshes']),
            'children': [],
            'translation': (segment.offset[0] / Dimension.SCALE_FACTOR, segment.offset[1] / Dimension.SCALE_FACTOR,
                            segment.offset[2] / Dimension.SCALE_FACTOR),
        }
        gltf['nodes'].append(node)
        index_accessor = len(gltf['accessors'])
        gltf['accessors'].append({
            'bufferView': 1,
            'byteOffset': buf_offset,
            'componentType': Gltf.UNSIGNED_SHORT,
            'count': index_count,
            'type': 'SCALAR',
            'max': [max_index],
            'min': [0],
        })
        gltf['meshes'].append({
            'primitives': [
                {
                    'attributes': {
                        'POSITION': 0,
                        'TEXCOORD_0': 1,
                    },
                    'indices': index_accessor,
                    'material': 0,
                },
            ],
        })

        for child in segment.children:
            cls._gltf_add_segment(gltf, node, buffer, child)

    def as_gltf(self) -> tuple[dict[str, Any], bytes, Image.Image]:
        stride = VERT_SIZE + UV_SIZE
        num_attrs = len(self.attributes)
        buffer = bytearray(num_attrs * stride)
        buf_len = 0
        tex_height = self.texture_height
        max_x = min_x = max_y = min_y = max_z = min_z = 0.
        for vert in self.attributes:
            x = vert[0] / Dimension.SCALE_FACTOR
            if x > max_x:
                max_x = x
            elif x < min_x:
                min_x = x

            y = vert[1] / Dimension.SCALE_FACTOR
            if y > max_y:
                max_y = y
            elif y < min_y:
                min_y = y

            z = vert[2] / Dimension.SCALE_FACTOR
            if z > max_z:
                max_z = z
            elif z < min_z:
                min_z = z

            u = vert[3] / TEXTURE_WIDTH
            v = (tex_height - vert[4]) / tex_height
            struct.pack_into('<5f', buffer, buf_len, x, y, z, u, v)
            buf_len += stride

        gltf: dict[str, Any] = {
            'asset': {
                'version': '2.0',
                'generator': 'galsdk',
            },
            'scene': 0,
            'scenes': [
                {
                    'nodes': [0],
                }
            ],
            'nodes': [
                {
                    'name': 'model',
                    'children': [],
                },
            ],
            'meshes': [],
            'images': [
                {
                    'uri': 'texture.png',
                },
            ],
            'samplers': [
                {
                    'magFilter': Gltf.NEAREST,
                    'minFilter': Gltf.NEAREST,
                },
            ],
            'textures': [
                {
                    'source': 0,
                    'sampler': 0,
                },
            ],
            'materials': [
                {
                    'pbrMetallicRoughness': {
                        'baseColorTexture': {
                            'index': 0,
                        },
                        'metallicFactor': 0.,
                        'roughnessFactor': 1.,
                    },
                },
            ],
            'buffers': [
                {
                    'uri': 'data.bin',
                    'byteLength': 0,
                },
            ],
            'bufferViews': [
                {
                    'buffer': 0,
                    'byteOffset': 0,
                    'byteLength': buf_len,
                    'byteStride': stride,
                    'target': Gltf.ARRAY_BUFFER,
                },
                {
                    'buffer': 0,
                    'byteOffset': buf_len,
                    'byteLength': 0,
                    'target': Gltf.ELEMENT_ARRAY_BUFFER,
                },
            ],
            'accessors': [
                {
                    'name': 'vertices',
                    'bufferView': 0,
                    'byteOffset': 0,
                    'componentType': Gltf.FLOAT,
                    'count': num_attrs,
                    'type': 'VEC3',
                    'min': [min_x, min_y, min_z],
                    'max': [max_x, max_y, max_z],
                },
                {
                    'name': 'texcoords',
                    'bufferView': 2,
                    'byteOffset': VERT_SIZE,
                    'componentType': Gltf.FLOAT,
                    'count': num_attrs,
                    'type': 'VEC2',
                    'min': [0., 0.],
                    'max': [1., 1.],
                },
            ],
        }

        root_node = gltf['nodes'][0]
        for root_segment in self.root_segments:
            self._gltf_add_segment(gltf, root_node, buffer, root_segment)

        final_buf = bytes(buffer)
        final_len = len(final_buf)
        gltf['buffers'][0]['byteLength'] = final_len
        gltf['bufferViews'][1]['byteLength'] = final_len - buf_len
        return gltf, final_buf, self.get_texture_image()

    def as_ply(self) -> str:
        tris, attributes = self._flatten()
        ply = f"""ply
format ascii 1.0
element vertex {len(attributes)}
property float x
property float y
property float z
element face {len(tris)}
property list uchar uint vertex_indices
end_header
"""
        for v in attributes:
            point = Point(v[0], v[1], v[2])
            ply += f'{point.panda_x} {point.panda_y} {point.panda_z}\n'
        for t in tris:
            ply += f'3 {t[0]} {t[1]} {t[2]}\n'

        return ply

    def as_obj(self, material_path: str = None, material_name: str = None,
               texture_path: str = None) -> tuple[str, str | None]:
        tris, attributes = self._flatten()
        obj = ''
        mtl = None
        if material_path is not None:
            obj += f'mtllib {material_path}\n'
        tex_height = self.texture_height
        for v in attributes:
            obj +=\
                f'v {v[0] / Dimension.SCALE_FACTOR} {v[1] / Dimension.SCALE_FACTOR} {v[2] / Dimension.SCALE_FACTOR}\n'\
                f'vt {v[3] / TEXTURE_WIDTH} {(tex_height - v[4]) / tex_height}\n'
        if material_name is not None:
            obj += f'usemtl {material_name}\n'
        for t in tris:
            obj += f'f {t[0] + 1}/{t[0] + 1} {t[1] + 1}/{t[1] + 1} {t[2] + 1}/{t[2] + 1}\n'

        if material_name is not None:
            mtl = f"""newmtl {material_name}
Ka 1.000 1.000 1.000
Kd 1.000 1.000 1.000
d 1.0
illum 0
"""
            if texture_path is not None:
                mtl += f'map_Kd {texture_path}\n'

        return obj, mtl

    @classmethod
    def import_(cls, path: Path, fmt: str = None) -> Self:
        raise NotImplementedError

    def export(self, path: Path, fmt: str = None) -> Path:
        if fmt is None:
            fmt = 'obj'
        if fmt[0] == '.':
            fmt = fmt[1:]

        match fmt.lower():
            case 'ply':
                new_path = path.with_suffix('.ply')
                new_path.write_text(self.as_ply())
            case 'obj':
                new_path = obj_path = path.with_suffix('.obj')
                mtl_path = path.with_suffix('.mtl')
                tex_path = path.with_suffix('.png')
                texture = self.get_texture_image()
                texture.save(tex_path)
                obj, mtl = self.as_obj(mtl_path.name, mtl_path.stem, tex_path.name)
                obj_path.write_text(obj)
                mtl_path.write_text(mtl)
            case 'bam':
                new_path = path.with_suffix('.bam')
                model = self.get_panda3d_model()
                texture = self.get_panda3d_texture()
                node = GeomNode('model_export')
                node.addGeom(model)
                node_path = NodePath(node)
                node_path.setTexture(texture)
                node_path.writeBamFile(util.panda_path(new_path))
            case 'tim':
                new_path = path.with_suffix('.tim')
                with new_path.open('wb') as f:
                    self.texture.write(f)
            case _:
                raise ValueError(f'Unknown format {fmt}')

        return new_path

    def write(self, f: BinaryIO, **kwargs):
        raise NotImplementedError

    def get_texture_image(self) -> Image:
        image = Image.new('RGBA', (TEXTURE_WIDTH, self.texture_height))
        for i in range(self.texture.num_palettes):
            # FIXME: the exact transparency level seems to vary from item to item and I don't know what controls it
            transparency = Transparency.SEMI if self.use_transparency and i > 0 else Transparency.NONE
            sub_image = self.texture.to_image(i, transparency)
            image.paste(sub_image, (0, TEXTURE_HEIGHT * i))
        return image

    @staticmethod
    def _read_chunk(f: BinaryIO, num_vertices: int, extra_len: int = 0) -> list[tuple[int, int, int, int, int]]:
        num_shorts = num_vertices * 3
        num_bytes = num_vertices * 2
        data_size = num_shorts * 2 + num_bytes
        count = util.int_from_bytes(f.read(2))
        attributes = []
        for k in range(count):
            data = f.read(data_size)
            raw_face = struct.unpack(f'{num_shorts}h{num_bytes}B', data)
            f.seek(extra_len, 1)
            for m in range(num_vertices):
                x, y, z = raw_face[m * 3:(m + 1) * 3]
                attributes.append((x, y, z, 0, 0))
            rest = raw_face[num_shorts:]
            for m in range(num_vertices):
                u = rest[m * 2]
                v = rest[m * 2 + 1]
                attr_index = m + k * num_vertices
                attrs = attributes[attr_index]
                attributes[attr_index] = (attrs[0], attrs[1], attrs[2], u, v)
        return attributes

    @staticmethod
    def _read_tim(f: BinaryIO) -> Tim:
        texture = f.read(0x8000)
        clut = f.read(0x80)

        tim = Tim()
        tim.set_clut(clut, CLUT_WIDTH)
        tim.set_image(texture, BitsPerPixel.BPP_4, BLOCK_WIDTH)
        assert tim.num_palettes == 4

        return tim

    @classmethod
    def _read_segment(cls, f: BinaryIO, attributes: dict[tuple[int, int, int, int, int], int],
                      offset: tuple[int, int, int] = (0, 0, 0)) -> Segment:
        clut_index = int.from_bytes(f.read(2), 'little')
        tri_attrs = []
        quad_attrs = []
        quad_attrs.extend(cls._read_chunk(f, 4))
        tri_attrs.extend(cls._read_chunk(f, 3))
        # the "extra" data is skipped by the game as well
        quad_attrs.extend(cls._read_chunk(f, 4, 0x18))
        tri_attrs.extend(cls._read_chunk(f, 3, 0x12))

        tri_attrs_final, quad_attrs_final = ([
            attributes.setdefault((x, y, z, u, v + TEXTURE_HEIGHT * clut_index), len(attributes))
            for x, y, z, u, v in attrs
        ] for attrs in [tri_attrs, quad_attrs])

        triangles = [
            (tri_attrs_final[i], tri_attrs_final[i + 1], tri_attrs_final[i + 2]) for i in range(0, len(tri_attrs), 3)
        ]
        quads = [
            (quad_attrs_final[i], quad_attrs_final[i + 1], quad_attrs_final[i + 2], quad_attrs_final[i + 3])
            for i in range(0, len(quad_attrs), 4)
        ]

        return Segment(clut_index, triangles, quads, offset)


class ActorModel(Model):
    """A 3D model of an actor (character)"""

    NUM_SEGMENTS = 19
    SEGMENT_ORDER = [0, 1, 2, 3, 4, 6, 7, 9, 10, 11, 12, 13, 14, 5, 15, 16, 8, 17, 18]

    def __init__(self, name: str, actor_id: int, attributes: list[tuple[int, int, int, int, int]],
                 root: Segment, texture: Tim):
        super().__init__(attributes, [root], texture)
        self.name = name
        self.id = actor_id

    @property
    def suggested_extension(self) -> str:
        return '.G3A'

    @classmethod
    def read(cls, f: BinaryIO, *, actor: Actor = None, **kwargs) -> ActorModel:
        if actor is None:
            # this is probably wrong, but FileFormat needs some refactoring if we want to make it mandatory
            actor = ACTORS[0]

        # a list of the x/y/z positions of each segment relative to its parent
        # the size of this list is not a multiple of 3, so the last number goes unused, and it also isn't long enough
        # to have entries for every segment, so the last 4 segments can't have their own translation
        offsets = struct.unpack('<46h', f.read(0x5c))
        tim = cls._read_tim(f)

        attributes = {}
        segments: list[Segment | None] = [None] * cls.NUM_SEGMENTS
        for i in cls.SEGMENT_ORDER:
            try:
                offset = (offsets[i * 3], offsets[i * 3 + 1], offsets[i * 3 + 2])
            except IndexError:
                offset = (0, 0, 0)
            segments[i] = cls._read_segment(f, attributes, offset)

        # this is the exact game logic
        root = segments[0]
        if actor.id in [LILIA.id, LEM.id]:
            root = root.add_child(segments[15])
        next_seg = root.add_child(segments[1])
        if actor.id == DOROTHY_EYE.id:
            next_seg.add_child(segments[2]).add_child(segments[3]).add_child(segments[4]).add_child(segments[5])\
                .add_child(segments[6])
        else:
            if actor.id in [HOTEL_KNOCK_GUY.id, HOTEL_RECEPTIONIST.id, LEM_ROBOT.id, JOULE.id]:
                next_seg = next_seg.add_child(segments[15])
            root2 = next_seg
            next_seg = next_seg.add_child(segments[2])
            if actor.id in [TERRORIST.id, PRIEST.id, CROVIC.id, CROVIC_ALT.id]:
                next_seg.add_child(segments[15]).add_child(segments[16])
            elif actor.id in [HOTEL_KNOCK_GUY.id, HOTEL_RECEPTIONIST.id, JOULE.id]:
                next_seg.add_child(segments[16]).add_child(segments[17])
            elif actor.id in [RION.id, RION_ALT_2.id, RION_PHONE.id, DANCER.id, CAIN.id, RION_ALT_1.id,
                              RAINHEART_HAT.id]:
                next_seg.add_child(segments[15])
            elif actor.id != LEM_ROBOT.id:
                next_seg.add_child(segments[17])

            next_seg = root2.add_child(segments[3])
            if actor.id == LEM_ROBOT.id:
                next_seg = next_seg.add_child(segments[16])
            next_seg = next_seg.add_child(segments[4]).add_child(segments[5])
            if actor.id in [RABBIT_KNIFE.id, HOTEL_GUN_GUY.id, GUARD_HAZARD_SUIT.id]:
                next_seg.add_child(segments[15])
            elif actor.id == CROVIC_ALT.id:
                next_seg.add_child(segments[17])
            elif actor.id in [RION.id, RION_PHONE.id]:
                next_seg.add_child(segments[16])

            next_seg = root2.add_child(segments[6])
            if actor.id == HOTEL_GUN_GUY.id:
                next_seg = next_seg.add_child(segments[18])
            next_seg = next_seg.add_child(segments[7]).add_child(segments[8])
            if actor.id == GUARD_HAZARD_SUIT.id:
                next_seg.add_child(segments[16]).add_child(segments[17])
            elif actor.id == LEM.id:
                next_seg.add_child(segments[16])
            elif actor.id == RION_ALT_2.id:
                next_seg.add_child(segments[16])

            root.add_child(segments[9]).add_child(segments[10]).add_child(segments[11])
            root.add_child(segments[12]).add_child(segments[13]).add_child(segments[14])

        return cls(actor.name, actor.id, list(attributes), segments[0], tim)


class ItemModel(Model):
    """A 3D model of an item"""

    MAX_SEGMENTS = 19

    def __init__(self, name: str, attributes: list[tuple[int, int, int, int, int]],
                 segments: list[Segment], texture: Tim, use_transparency: bool = False):
        super().__init__(attributes, segments, texture, use_transparency)
        self.name = name

    @property
    def suggested_extension(self) -> str:
        return '.G3I'

    @classmethod
    def sniff(cls, f: BinaryIO) -> Self | None:
        try:
            model = cls.read(f, strict_mode=True)
            if len(model.attributes) > 0:
                return model
            return None
        except Exception:
            return None

    @classmethod
    def read(cls, f: BinaryIO, *, name: str = '', use_transparency: bool = False, strict_mode: bool = False,
             **kwargs) -> ItemModel:
        tim = cls._read_tim(f)

        attributes = {}
        segments = []
        for _ in range(cls.MAX_SEGMENTS):
            try:
                segments.append(cls._read_segment(f, attributes))
            except ValueError:
                # MODEL.CDB 92 and 93 fail to load with this enabled, but it's appropriate for sniffing
                if strict_mode:
                    raise
                break
            except struct.error:
                break
        return cls(name, list(attributes), segments, tim, use_transparency)


def export(model_path: str, target_path: str, actor_id: int | None):
    model_path = Path(model_path)
    target_path = Path(target_path)
    with model_path.open('rb') as f:
        if actor_id is None:
            model = ItemModel.read(f)
        else:
            model = ActorModel.read(f, actor=ACTORS[actor_id])
    model.export(target_path, target_path.suffix)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Export Galerians 3D models and textures')
    parser.add_argument('-a', '--actor', type=int, help='The given model file is an actor model. The argument should '
                        'be the ID of the actor the model belongs to.')
    parser.add_argument('model', help='The model file to be exported')
    parser.add_argument('target', help='The path to export the model to. The format will be detected from the file '
                        'extension. Supported extensions are ply, obj, bam, and tim (in which case only the texture '
                        'will be exported).')

    args = parser.parse_args()
    export(args.model, args.target, args.actor)
