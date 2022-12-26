from __future__ import annotations

import functools
import io
import struct
from dataclasses import dataclass
from typing import BinaryIO

from panda3d.core import Geom, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter, PNMImage,\
    StringStream, Texture
from PIL import Image

from psx.tim import BitsPerPixel, Tim, Transparency


@dataclass
class Vertex:
    vertex_index: int
    uv_index: int


@dataclass
class Actor:
    name: str
    id: int
    skeleton: dict[int, list[int]]
    model_index: int = None


RION = Actor('Rion', 0, {
    0: 0,  # waist
    1: [0, 1],  # torso
    2: [0, 1, 2],  # hair
    3: [0, 1, 3],  # right shoulder
    4: [0, 1, 3, 4],  # right forearm
    5: [0, 1, 6],  # left shoulder
    6: [0, 1, 6, 7],  # left forearm
    7: [0, 9],  # right thigh
    8: [0, 9, 10],  # right shin
    9: [0, 9, 10, 11],  # right foot
    10: [0, 12],  # left thigh
    11: [0, 12, 13],  # left shin
    12: [0, 12, 13, 14],  # left foot
    13: [0, 1, 3, 4, 5],  # right hand
    # 14:
    # Rion (0), Cain (6), Crovic (7), hotel girl (23), hotel terrorist (26), face/head = [0, 1, 2]
    # Joule (8), hotel knock guy (22), hotel front desk guy (24), upper torso = [0, 1]
    # Rabbit (19), hotel gun guy (25), knife/bottle = [0, 1, 3, 4, 5]
    # everyone else, skirt = 0
    14: [0, 1, 2],
    # 15:
    # Rion (0), Beeject = [0, 1, 3, 4, 5]
    # Crovic (7), hotel knock guy (22/32), face = [0, 1, 2]
    # robot Lem (9), right bicep = [0, 1, 3]
    # Rion with phone (36), phone = not sure; doesn't seem to be rotated correctly. Beeject pos might be best
    15: [0, 1, 3, 4, 5],
    16: [0, 1, 6, 7, 8],  # left hand
    # 17:
    # Joule (8), robot Lem (9), head = [0, 1, 2]
    # Crovic holding(?) sheet, sheet = [0, 1, 3, 4, 5] (this is a guess)
    17: [0, 1, 3, 4, 5],
    # 18:
    # robot Lem (9), left bicep = [0, 1, 6]
    18: [0, 1, 6],
})
LILIA = Actor('Lilia', 1, {
    **RION.skeleton,
    14: [0],
})
LEM = Actor('Lem', 2, LILIA.skeleton)
BIRDMAN = Actor('Birdman', 3, LILIA.skeleton)
RAINHEART = Actor('Rainheart', 4, LILIA.skeleton)
RITA = Actor('Rita', 5, LILIA.skeleton)
CAIN = Actor('Cain', 6, RION.skeleton)
CROVIC = Actor('Crovic', 7, {
    **RION.skeleton,
    15: [0, 1, 2],
})
JOULE = Actor('Joule', 8, {
    **RION.skeleton,
    14: [0, 1],
    15: [0, 1, 2],
    17: [0, 1, 2],
})
LEM_ROBOT = Actor('Robot Lem', 9, {
    **LILIA.skeleton,
    15: [0, 1, 3],
    17: [0, 1, 2],
})
GUARD_HOSPITAL_SKINNY = Actor('Hospital Guard (skinny)', 10, LILIA.skeleton)
GUARD_HOSPITAL_BURLY = Actor('Hospital Guard (burly)', 11, LILIA.skeleton)
GUARD_HOSPITAL_GLASSES = Actor('Hospital Guard (sunglasses)', 12, LILIA.skeleton)
GUARD_MECH_SUIT = Actor('Mech Suit Guard', 13, LILIA.skeleton)
GUARD_HAZARD_SUIT = Actor('Hazard Suit Guard', 14, {
    **RION.skeleton,
    14: [0, 1, 3, 4, 5],
    17: [0, 1, 6, 7, 8],
})
SNIPER = Actor('Sniper', 15, LILIA.skeleton)
DOCTOR_BROWN_HAIR = Actor('Doctor (brown hair)', 16, LILIA.skeleton)
DOCTOR_BLONDE = Actor('Doctor (blonde)', 17, LILIA.skeleton)
DOCTOR_BALD = Actor('Doctor (bald)', 18, LILIA.skeleton)
RABBIT_KNIFE = Actor('Rabbit (knife)', 19, {
    **RION.skeleton,
    14: [0, 1, 3, 4, 5],
})
RABBIT_TRENCH_COAT = Actor('Rabbit (trench coat)', 20, LILIA.skeleton)
ARABESQUE_BIPED = Actor('Arabesque (biped)', 21, LILIA.skeleton)
HOTEL_KNOCK_GUY = Actor('Hotel knock guy', 22, {
    **RION.skeleton,
    14: [0, 1],
    15: [0, 1, 2],
    17: [0, 1, 2],
})
DANCER = Actor('Dancer', 23, RION.skeleton)
HOTEL_RECEPTIONIST = Actor('Hotel Receptionist', 24, JOULE.skeleton)
HOTEL_GUN_GUY = Actor('Hotel gun guy', 25, {
    **RION.skeleton,
    14: [0, 1, 3, 4, 5]
})
TERRORIST = Actor('Terrorist', 26, {
    **RION.skeleton,
    15: [0, 1, 2],
})
PRIEST = Actor('Priest', 27, TERRORIST.skeleton)
RAINHEART_HAT = Actor('Rainheart (bellhop hat)', 28, RION.skeleton)
MECH_SUIT_ALT = Actor('Mech Suit (unused?)', 29, LILIA.skeleton)
RABBIT_UNARMED = Actor('Rabbit (unarmed)', 30, LILIA.skeleton)
ARABESQUE_QUADRUPED = Actor('Arabesque (quadruped)', 31, LILIA.skeleton)
HOTEL_KNOCK_GUY_2 = Actor('Hotel knock guy 2', 32, HOTEL_KNOCK_GUY.skeleton)
UNKNOWN_ACTOR = Actor('Unknown', 33, LILIA.skeleton)
CROVIC_ALT = Actor('Crovic (holding something)', 34, CROVIC.skeleton)
DOROTHY_EYE = Actor("Dorothy's eye", 35, {
    0: 0,  # eye
    1: [0, 1],  # tail segments
    2: [0, 1, 2],
    3: [0, 1, 2, 3],
    4: [0, 1, 2, 3, 4],
    5: [0, 1, 2, 3, 4, 5],
    6: [0, 1, 2, 3, 4, 5, 6],
})
RION_PHONE = Actor('Rion (with phone)', 36, RION.skeleton)
RION_ALT_1 = Actor('Rion (alternate #1)', 37, RION.skeleton)
RION_ALT_2 = Actor('Rion (alternate #2)', 38, RION.skeleton)

UNKNOWN_UNUSED = Actor('Unknown (unused)', 39, RION.skeleton, 20)
DOCTOR_UNUSED_1 = Actor('Doctor (unused #1)', 40, RION.skeleton, 38)
DOCTOR_UNUSED_2 = Actor('Doctor (unused #2)', 41, RION.skeleton, 40)
DOCTOR_UNUSED_3 = Actor('Doctor (unused #3)', 42, RION.skeleton, 42)
RION_UNUSED = Actor('Rion (unused)', 43, RION.skeleton, 77)

ACTORS = [
    RION, LILIA, LEM, BIRDMAN, RAINHEART, RITA, CAIN, CROVIC, JOULE, LEM_ROBOT, GUARD_HOSPITAL_SKINNY,
    GUARD_HOSPITAL_BURLY, GUARD_HOSPITAL_GLASSES, GUARD_MECH_SUIT, GUARD_HAZARD_SUIT, SNIPER, DOCTOR_BROWN_HAIR,
    DOCTOR_BLONDE, DOCTOR_BALD, RABBIT_KNIFE, RABBIT_TRENCH_COAT, ARABESQUE_BIPED, HOTEL_KNOCK_GUY, DANCER,
    HOTEL_RECEPTIONIST, HOTEL_GUN_GUY, TERRORIST, PRIEST, RAINHEART_HAT, MECH_SUIT_ALT, RABBIT_UNARMED,
    ARABESQUE_QUADRUPED, HOTEL_KNOCK_GUY_2, UNKNOWN_ACTOR, CROVIC_ALT, DOROTHY_EYE, RION_PHONE, RION_ALT_1, RION_ALT_2,
    UNKNOWN_UNUSED, DOCTOR_UNUSED_1, DOCTOR_UNUSED_2, DOCTOR_UNUSED_3, RION_UNUSED,
]

CLUT_WIDTH = 16
BLOCK_WIDTH = 64
TEXTURE_WIDTH = 0x100
TEXTURE_HEIGHT = 0x100
SCALE_FACTOR = 64


class Model:
    """A 3D model of a game object"""

    def __init__(self, vertices: list[tuple[int, int, int]],
                 uvs: list[tuple[int, int]], triangles: list[tuple[Vertex, Vertex, Vertex]],
                 quads: list[tuple[Vertex, Vertex, Vertex, Vertex]], texture: Tim, use_transparency: bool = False):
        self.vertices = vertices
        self.uvs = uvs
        self.triangles = triangles
        self.quads = quads
        self.texture = texture
        self.use_transparency = use_transparency

    @functools.cache
    def get_panda3d_model(self) -> Geom:
        # convert quads to triangles
        triangles = [*self.triangles]
        for q in self.quads:
            triangles.append((q[0], q[1], q[3]))
            triangles.append((q[3], q[2], q[0]))

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

        vdata = GeomVertexData('', GeomVertexFormat.getV3t2(), Geom.UHStatic)
        vdata.setNumRows(len(vertices))

        vertex = GeomVertexWriter(vdata, 'vertex')
        texcoord = GeomVertexWriter(vdata, 'texcoord')
        tex_height = self.texture_height
        for x, y, z, u, v in vertices:
            vertex.addData3(-x / SCALE_FACTOR, z / SCALE_FACTOR, y / SCALE_FACTOR)
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

    def as_ply(self) -> str:
        ply = f"""ply
format ascii 1.0
element vertex {len(self.vertices)}
property float x
property float y
property float z
element face {len(self.quads) + len(self.triangles)}
property list uchar uint vertex_indices
end_header
"""
        for v in self.vertices:
            ply += f'{-v[0] / SCALE_FACTOR} {v[2] / SCALE_FACTOR} {v[1] / SCALE_FACTOR}\n'
        for t in self.triangles:
            ply += f'3 {t[0].vertex_index} {t[1].vertex_index} {t[2].vertex_index}\n'
        for q in self.quads:
            ply += f'4 {q[0].vertex_index} {q[1].vertex_index} {q[3].vertex_index} {q[2].vertex_index}\n'

        return ply

    def as_obj(self, material_path: str = None, material_name: str = None,
               texture_path: str = None) -> tuple[str, str | None]:
        obj = ''
        mtl = None
        if material_path is not None:
            obj += f'mtllib {material_path}\n'
        for v in self.vertices:
            obj += f'v {v[0] / SCALE_FACTOR} {v[1] / SCALE_FACTOR} {v[2] / SCALE_FACTOR}\n'
        tex_height = self.texture_height
        for u in self.uvs:
            obj += f'vt {u[0] / TEXTURE_WIDTH} {(tex_height - u[1]) / tex_height}\n'
        if material_name is not None:
            obj += f'usemtl {material_name}\n'
        for t in self.triangles:
            obj += f'f {t[0].vertex_index + 1}/{t[0].uv_index + 1} {t[1].vertex_index + 1}/{t[1].uv_index + 1} ' +\
                   f'{t[2].vertex_index + 1}/{t[2].uv_index + 1}\n'
        for q in self.quads:
            obj += f'f {q[0].vertex_index + 1}/{q[0].uv_index + 1} {q[1].vertex_index + 1}/{q[1].uv_index + 1} ' +\
                   f'{q[3].vertex_index + 1}/{q[3].uv_index + 1} {q[2].vertex_index + 1}/{q[2].uv_index + 1}\n'

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

    def get_texture_image(self) -> Image:
        image = Image.new('RGBA', (TEXTURE_WIDTH, self.texture_height))
        for i in range(self.texture.num_palettes):
            # FIXME: the exact transparency level seems to vary from item to item and I don't know what controls it
            transparency = Transparency.SEMI if self.use_transparency and i > 0 else Transparency.NONE
            sub_image = self.texture.to_image(i, transparency)
            image.paste(sub_image, (0, TEXTURE_HEIGHT * i))
        return image

    @staticmethod
    def _read_chunk(f: BinaryIO, num_vertices: int, extra_len: int = 0) -> tuple[
        list[tuple[int, int, int]], list[tuple[int, int]]
    ]:
        num_shorts = num_vertices * 3
        num_bytes = num_vertices * 2
        data_size = num_shorts * 2 + num_bytes
        count = int.from_bytes(f.read(2), 'little')
        verts = []
        tex = []
        for k in range(count):
            data = f.read(data_size)
            raw_face = struct.unpack(f'{num_shorts}h{num_bytes}B', data)
            f.seek(extra_len, 1)
            for m in range(num_vertices):
                x, y, z = raw_face[m * 3:(m + 1) * 3]
                verts.append((x, y, z))
            rest = raw_face[num_shorts:]
            for m in range(num_vertices):
                tex.append((rest[m * 2], rest[m * 2 + 1]))
        return verts, tex

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
    def _read_bone(cls, f: BinaryIO, vertices: dict[tuple[int, int, int], int],
                   uvs: dict[tuple[int, int], int],
                   triangles: list[tuple[Vertex, Vertex, Vertex]],
                   quads: list[tuple[Vertex, Vertex, Vertex, Vertex]],
                   offset: tuple[int, int, int] = (0, 0, 0)):
        clut_index = int.from_bytes(f.read(2), 'little')
        tri_verts = []
        tri_uvs = []
        quad_verts = []
        quad_uvs = []
        v, u = cls._read_chunk(f, 4)
        quad_verts.extend(v)
        quad_uvs.extend(u)
        v, u = cls._read_chunk(f, 3)
        tri_verts.extend(v)
        tri_uvs.extend(u)
        # TODO: the "extra" data is probably normals
        v, u = cls._read_chunk(f, 4, 0x18)
        quad_verts.extend(v)
        quad_uvs.extend(u)
        v, u = cls._read_chunk(f, 3, 0x12)
        tri_verts.extend(v)
        tri_uvs.extend(u)

        tri_verts = [(tv[0] + offset[0], tv[1] + offset[1], tv[2] + offset[2]) for tv in tri_verts]
        quad_verts = [(qv[0] + offset[0], qv[1] + offset[1], qv[2] + offset[2]) for qv in quad_verts]

        # we'll stack each palette into one image
        tri_uvs = [(tu[0], tu[1] + TEXTURE_HEIGHT * clut_index) for tu in tri_uvs]
        quad_uvs = [(qu[0], qu[1] + TEXTURE_HEIGHT * clut_index) for qu in quad_uvs]

        for j in range(len(tri_verts)):
            if tri_verts[j] not in vertices:
                vertices[tri_verts[j]] = len(vertices)
            vert_index = vertices[tri_verts[j]]

            if tri_uvs[j] not in uvs:
                uvs[tri_uvs[j]] = len(uvs)
            uv_index = uvs[tri_uvs[j]]
            tri_verts[j] = Vertex(vert_index, uv_index)

        for j in range(len(quad_verts)):
            if quad_verts[j] not in vertices:
                vertices[quad_verts[j]] = len(vertices)
            vert_index = vertices[quad_verts[j]]

            if quad_uvs[j] not in uvs:
                uvs[quad_uvs[j]] = len(uvs)
            uv_index = uvs[quad_uvs[j]]
            quad_verts[j] = Vertex(vert_index, uv_index)

        for j in range(0, len(tri_verts), 3):
            triangles.append((tri_verts[j], tri_verts[j + 1], tri_verts[j + 2]))

        for j in range(0, len(quad_verts), 4):
            quads.append((quad_verts[j], quad_verts[j + 1], quad_verts[j + 2], quad_verts[j + 3]))


class ActorModel(Model):
    """A 3D model of an actor (character)"""

    NUM_BONES = 19

    def __init__(self, name: str, actor_id: int, vertices: list[tuple[int, int, int]],
                 uvs: list[tuple[int, int]], triangles: list[tuple[Vertex, Vertex, Vertex]],
                 quads: list[tuple[Vertex, Vertex, Vertex, Vertex]], texture: Tim):
        super().__init__(vertices, uvs, triangles, quads, texture)
        self.name = name
        self.id = actor_id

    @classmethod
    def read(cls, actor: Actor, f: BinaryIO) -> ActorModel:
        # a list of the x/y/z positions of each bone relative to its parent
        # the size of this list is not a multiple of 3, so the last number goes unused, and it also isn't long enough
        # to have entries for every bone, so the last 4 bones can't be the parent of another bone
        offsets = struct.unpack('46h', f.read(0x5c))
        tim = cls._read_tim(f)

        vertices = {}
        uvs = {}
        triangles: list[tuple[Vertex, Vertex, Vertex]] = []
        quads: list[tuple[Vertex, Vertex, Vertex, Vertex]] = []
        for i in range(cls.NUM_BONES):
            match actor.skeleton.get(i):
                case [*indexes]:
                    offset = (0, 0, 0)
                    for index in indexes:
                        offset = (
                            offset[0] + offsets[index * 3],
                            offset[1] + offsets[index * 3 + 1],
                            offset[2] + offsets[index * 3 + 2],
                        )
                case None:
                    # debug code to shift any unknown parts off to the side where we can get a better look at them
                    offset = (i * 0x80, -0x40 if (i & 1) == 1 else 0x40, 0)
                case index:
                    offset = (offsets[index * 3], offsets[index * 3 + 1], offsets[index * 3 + 2])
            cls._read_bone(f, vertices, uvs, triangles, quads, offset)

        return cls(actor.name, actor.id, list(vertices), list(uvs), triangles, quads, tim)


class ItemModel(Model):
    """A 3D model of an item"""

    MAX_BONES = 19

    def __init__(self, name: str, vertices: list[tuple[int, int, int]],
                 uvs: list[tuple[int, int]], triangles: list[tuple[Vertex, Vertex, Vertex]],
                 quads: list[tuple[Vertex, Vertex, Vertex, Vertex]], texture: Tim, use_transparency: bool = False):
        super().__init__(vertices, uvs, triangles, quads, texture, use_transparency)
        self.name = name

    @classmethod
    def read(cls, name: str, f: BinaryIO, use_transparency: bool = False) -> ItemModel:
        tim = cls._read_tim(f)

        vertices = {}
        uvs = {}
        triangles = []
        quads = []
        for _ in range(cls.MAX_BONES):
            try:
                cls._read_bone(f, vertices, uvs, triangles, quads)
            except struct.error:
                break
        return cls(name, list(vertices), list(uvs), triangles, quads, tim, use_transparency)
