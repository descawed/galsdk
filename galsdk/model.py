from __future__ import annotations

import functools
import io
import json
import struct
from abc import abstractmethod
from dataclasses import dataclass, replace
from enum import IntEnum
from pathlib import Path
from typing import Any, BinaryIO, Container, Iterator, Self, Sequence

import numpy as np
from panda3d.core import Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter, NodePath,\
    PandaNode, PNMImage, StringStream, Texture
from PIL import Image, ImageDraw

from galsdk import file, graphics
from galsdk.animation import Animation, AnimationDb
from galsdk.coords import Dimension, Point
from galsdk.format import FileFormat
from psx.tim import BitsPerPixel, Tim, Transparency


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


class Glb(IntEnum):
    VERSION = 2
    MAGIC = 0x46546C67
    JSON = 0x4E4F534A
    BIN = 0x004E4942


@dataclass(eq=True, frozen=True)
class Vertex:
    x: int
    y: int
    z: int
    u: int
    v: int
    nx: int = None
    ny: int = None
    nz: int = None
    has_original_normals: bool = False

    def with_uv(self, u: int, v: int) -> Self:
        return replace(self, u=u, v=v)

    def with_normal(self, nx: int, ny: int, nz: int, is_original: bool = True) -> Self:
        return replace(self, nx=nx, ny=ny, nz=nz, has_original_normals=is_original)

    @property
    def normal(self) -> np.ndarray:
        norm = Point(self.nx, self.ny, self.nz).ndarray
        if np.all(norm == 0):
            return norm

        norm /= np.linalg.norm(norm)
        return norm


class Segment:
    def __init__(self, index: int, clut_index: int, triangles: list[tuple[int, int, int]],
                 quads: list[tuple[int, int, int, int]], offset: tuple[int, int, int] = (0, 0, 0),
                 total_offset: tuple[int, int, int] = None, children: list[Segment] = None,
                 can_change_translation: bool = False, file_index: int = None,
                 has_transparency: bool = False):
        self.index = index
        self.clut_index = clut_index
        self.triangles = triangles
        self.quads = quads
        self.offset = offset
        self.total_offset = total_offset or offset
        self.children = children or []
        self.can_change_translation = can_change_translation
        self.file_index = index if file_index is None else file_index
        self.has_transparency = has_transparency

    def __len__(self) -> int:
        return 1 + sum(len(child) for child in self.children)

    @property
    def all_triangles(self) -> Iterator[tuple[int, int, int]]:
        yield from self.triangles
        for q in self.quads:
            yield q[0], q[1], q[3]
            yield q[3], q[2], q[0]

    def as_node_path(self, vdata: GeomVertexData) -> NodePath:
        primitive = GeomTriangles(Geom.UHStatic)

        for tri in self.all_triangles:
            # the -x when adding the vertex data means we have to reverse the vertices for proper winding order
            primitive.addVertices(tri[2], tri[1], tri[0])

        primitive.closePrimitive()

        geom = Geom(vdata)
        geom.addPrimitive(primitive)
        node = GeomNode(f'segment{self.index}')
        node.addGeom(geom)
        node_path = NodePath(node)
        translation = Point(*self.offset)
        node_path.setPos(translation.panda_x, translation.panda_y, translation.panda_z)
        node_path.setTag('index', str(self.index))

        for child in self.children:
            child_path = child.as_node_path(vdata)
            child_path.reparentTo(node_path)

        return node_path

    def flatten(self, new_attributes: dict[Vertex, int], original_attributes: list[Vertex],
                rotations: list[np.ndarray] = None, parent_transform: np.ndarray = None) -> list[tuple[int, int, int]]:
        if rotations and self.index < len(rotations):
            rotation = rotations[self.index]
        else:
            rotation = np.array([0, 0, 0])

        if parent_transform is None:
            parent_transform = np.identity(4)

        sines = np.sin(rotation)
        cosines = np.cos(rotation)
        x_rot = np.array([[1., 0., 0.],
                          [0., cosines[0], -sines[0]],
                          [0., sines[0], cosines[0]]])
        y_rot = np.array([[cosines[1], 0., sines[1]],
                          [0., 1., 0.],
                          [-sines[1], 0., cosines[1]]])
        z_rot = np.array([[cosines[2], -sines[2], 0.],
                          [sines[2], cosines[2], 0.],
                          [0., 0., 1.]])
        local_transform = np.identity(4)
        local_transform[:3, :3] = x_rot @ y_rot @ z_rot
        local_transform[:3, 3] = np.array(self.offset) / 4096
        transform = parent_transform @ local_transform
        new_tris = []
        for tri in self.all_triangles:
            new_tri = []
            for index in tri:
                v = original_attributes[index]
                vert = np.array([v.x / 4096, v.y / 4096, v.z / 4096, 1.])
                transformed = transform @ vert
                cartesian = transformed[:3] / transformed[3]
                normal = np.array([v.nx / 4096, v.ny / 4096, v.nz / 4096, 1.])
                transformed_normal = transform @ normal
                cartesian_normal = transformed_normal[:3] / transformed_normal[3]
                new_vert = replace(v, x=int(cartesian[0] * 4096), y=int(cartesian[1] * 4096), z=int(cartesian[2] * 4096),
                                   nx=int(cartesian_normal[0] * 4096), ny=int(cartesian_normal[1] * 4096), nz=int(cartesian_normal[2] * 4096))
                new_tri.append(new_attributes.setdefault(new_vert, len(new_attributes)))
            new_tris.append(tuple(new_tri))
        for child in self.children:
            child_tris = child.flatten(new_attributes, original_attributes, rotations, transform)
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
    skeleton: dict[int, dict[int, dict[int, dict[int, dict[int, dict[int, dict[int, dict[int, dict[int, int]]]]]]]]]
    model_index: int = None


RION = Actor('Rion', 0, {
    0: {
        1: {
            2: {15: {}},
            3: {4: {5: {16: {}}}},
            6: {7: {8: {}}},
        },
        9: {10: {11: {}}},
        12: {13: {14: {}}},
    },
})
LILIA = Actor('Lilia', 1, {
    0: {
        15: {
            1: {
                2: {},
                3: {4: {5: {}}},
                6: {7: {8: {}}},
            },
            9: {10: {11: {}}},
            12: {13: {14: {}}},
        },
    },
})
LEM = Actor('Lem', 2, {
    0: {
        15: {
            1: {
                2: {},
                3: {4: {5: {}}},
                6: {7: {8: {16: {}}}},
            },
            9: {10: {11: {}}},
            12: {13: {14: {}}},
        },
    },
})
BIRDMAN = Actor('Birdman', 3, {
    0: {
        1: {
            2: {},
            3: {4: {5: {}}},
            6: {7: {8: {}}},
        },
        9: {10: {11: {}}},
        12: {13: {14: {}}},
    },
})
RAINHEART = Actor('Rainheart', 4, BIRDMAN.skeleton)
RITA = Actor('Rita', 5, BIRDMAN.skeleton)
CAIN = Actor('Cain', 6, {
    0: {
        1: {
            2: {15: {}},
            3: {4: {5: {}}},
            6: {7: {8: {}}},
        },
        9: {10: {11: {}}},
        12: {13: {14: {}}},
    },
})
CROVIC = Actor('Crovic', 7, {
    0: {
        1: {
            2: {15: {16: {}}},
            3: {4: {5: {}}},
            6: {7: {8: {}}},
        },
        9: {10: {11: {}}},
        12: {13: {14: {}}},
    },
})
JOULE = Actor('Joule', 8, {
    0: {
        1: {
            15: {
                2: {16: {17: {}}},
                3: {4: {5: {}}},
                6: {7: {8: {}}},
            },
        },
        9: {10: {11: {}}},
        12: {13: {14: {}}},
    },
})
LEM_ROBOT = Actor('Robot Lem', 9, {
    0: {
        1: {
            15: {
                2: {17: {}},
                3: {16: {4: {5: {}}}},
                6: {7: {8: {}}},
            },
        },
        9: {10: {11: {}}},
        12: {13: {14: {}}},
    },
})
GUARD_HOSPITAL_SKINNY = Actor('Hospital Guard (skinny)', 10, BIRDMAN.skeleton)
GUARD_HOSPITAL_BURLY = Actor('Hospital Guard (burly)', 11, BIRDMAN.skeleton)
GUARD_HOSPITAL_GLASSES = Actor('Hospital Guard (sunglasses)', 12, BIRDMAN.skeleton)
GUARD_MECH_SUIT = Actor('Mech Suit Guard', 13, BIRDMAN.skeleton)
GUARD_HAZARD_SUIT = Actor('Hazard Suit Guard', 14, {
    0: {
        1: {
            2: {},
            3: {4: {5: {15: {}}}},
            6: {7: {8: {16: {17: {}}}}},
        },
        9: {10: {11: {}}},
        12: {13: {14: {}}},
    },
})
SNIPER = Actor('Sniper', 15, BIRDMAN.skeleton)
DOCTOR_BROWN_HAIR = Actor('Doctor (brown hair)', 16, BIRDMAN.skeleton)
DOCTOR_BLONDE = Actor('Doctor (blonde)', 17, BIRDMAN.skeleton)
DOCTOR_BALD = Actor('Doctor (bald)', 18, BIRDMAN.skeleton)
RABBIT_KNIFE = Actor('Rabbit (knife)', 19, {
    0: {
        1: {
            2: {},
            3: {4: {5: {15: {}}}},
            6: {7: {8: {}}},
        },
        9: {10: {11: {}}},
        12: {13: {14: {}}},
    },
})
RABBIT_TRENCH_COAT = Actor('Rabbit (trench coat)', 20, BIRDMAN.skeleton)
ARABESQUE_BIPED = Actor('Arabesque (biped)', 21, BIRDMAN.skeleton)
HOTEL_KNOCK_GUY = Actor('Hotel knock guy', 22, JOULE.skeleton)
DANCER = Actor('Suzan', 23, {
    0: {
        1: {
            2: {15: {}},
            3: {4: {5: {}}},
            6: {7: {8: {}}},
        },
        9: {10: {11: {}}},
        12: {13: {14: {}}},
    },
})
HOTEL_RECEPTIONIST = Actor('Hotel Receptionist', 24, JOULE.skeleton)
HOTEL_GUN_GUY = Actor('Hotel gun guy', 25, {
    0: {
        1: {
            2: {},
            3: {4: {5: {15: {}}}},
            6: {18: {7: {8: {}}}},
        },
        9: {10: {11: {}}},
        12: {13: {14: {}}},
    },
})
TERRORIST = Actor('Terrorist', 26, CROVIC.skeleton)
PRIEST = Actor('Priest', 27, CROVIC.skeleton)
RAINHEART_HAT = Actor('Rainheart (bellhop hat)', 28, DANCER.skeleton)
MECH_SUIT_ALT = Actor('Mech Suit (unused?)', 29, BIRDMAN.skeleton)
RABBIT_UNARMED = Actor('Rabbit (unarmed)', 30, BIRDMAN.skeleton)
ARABESQUE_QUADRUPED = Actor('Arabesque (quadruped)', 31, BIRDMAN.skeleton)
HOTEL_KNOCK_GUY_2 = Actor('Hotel knock guy 2', 32, JOULE.skeleton)
RAINHEART_SUMMON_ACTOR = Actor('Rainheart summon', 33, BIRDMAN.skeleton)
CROVIC_ALT = Actor('Crovic (holding something)', 34, {
    0: {
        1: {
            2: {15: {16: {}}},
            3: {4: {5: {17: {}}}},
            6: {7: {8: {}}},
        },
        9: {10: {11: {}}},
        12: {13: {14: {}}},
    },
})
DOROTHY_EYE = Actor("Dorothy's eye", 35, {0: {1: {2: {3: {4: {6: {5: {7: {}}}}}}}}})
RION_PHONE = Actor('Rion (with phone)', 36, RION.skeleton)
RION_ALT_1 = Actor('Rion (alternate #1)', 37, DANCER.skeleton)
RION_ALT_2 = Actor('Rion (alternate #2)', 38, {
    0: {
        1: {
            2: {15: {}},
            3: {4: {5: {}}},
            6: {7: {8: {16: {}}}},
        },
        9: {10: {11: {}}},
        12: {13: {14: {}}},
    },
})

RAINHEART_SUMMON_UNUSED = Actor('Rainheart summon (unused)', 39, BIRDMAN.skeleton, 20)
DOCTOR_UNUSED_1 = Actor('Doctor (unused #1)', 40, BIRDMAN.skeleton, 38)
DOCTOR_UNUSED_2 = Actor('Doctor (unused #2)', 41, BIRDMAN.skeleton, 40)
DOCTOR_UNUSED_3 = Actor('Doctor (unused #3)', 42, BIRDMAN.skeleton, 42)
RION_UNUSED = Actor('Rion (unused)', 43, RION.skeleton, 77)

ACTORS = [
    RION, LILIA, LEM, BIRDMAN, RAINHEART, RITA, CAIN, CROVIC, JOULE, LEM_ROBOT, GUARD_HOSPITAL_SKINNY,
    GUARD_HOSPITAL_BURLY, GUARD_HOSPITAL_GLASSES, GUARD_MECH_SUIT, GUARD_HAZARD_SUIT, SNIPER, DOCTOR_BROWN_HAIR,
    DOCTOR_BLONDE, DOCTOR_BALD, RABBIT_KNIFE, RABBIT_TRENCH_COAT, ARABESQUE_BIPED, HOTEL_KNOCK_GUY, DANCER,
    HOTEL_RECEPTIONIST, HOTEL_GUN_GUY, TERRORIST, PRIEST, RAINHEART_HAT, MECH_SUIT_ALT, RABBIT_UNARMED,
    ARABESQUE_QUADRUPED, HOTEL_KNOCK_GUY_2, RAINHEART_SUMMON_ACTOR, CROVIC_ALT, DOROTHY_EYE, RION_PHONE, RION_ALT_1,
    RION_ALT_2, RAINHEART_SUMMON_UNUSED, DOCTOR_UNUSED_1, DOCTOR_UNUSED_2, DOCTOR_UNUSED_3, RION_UNUSED,
]

ZANMAI_ACTORS = [
    RION, LEM, RAINHEART, RITA, replace(GUARD_HOSPITAL_SKINNY, id=8), replace(GUARD_HOSPITAL_BURLY, id=9),
    replace(GUARD_HOSPITAL_GLASSES, id=10), Actor('Doctor (brown hair) (18)', 18, BIRDMAN.skeleton),
    Actor('Doctor (blonde) (19)', 19, BIRDMAN.skeleton), Actor('Doctor (bald) (20)', 20, BIRDMAN.skeleton),
    Actor('Rabbit #1', 23, BIRDMAN.skeleton), Actor('Rabbit #2', 24, BIRDMAN.skeleton),
    Actor('Doctor (brown hair) (27)', 27, BIRDMAN.skeleton), Actor('Doctor (blonde) (28)', 28, BIRDMAN.skeleton),
    Actor('Doctor (bald) (29)', 29, BIRDMAN.skeleton),
    # unused models
    Actor('Birdman', 100, BIRDMAN.skeleton, 4), Actor('Crovic', 101, CROVIC.skeleton, 5),
    Actor('Rainheart summon', 102, RAINHEART_SUMMON_ACTOR.skeleton, 6), Actor('Joule', 103, JOULE.skeleton, 23),
    Actor('Lilia', 104, LILIA.skeleton, 33), Actor('Rion (unused)', 105, RION.skeleton, 50),
    Actor('Robot Lem', 106, LEM_ROBOT.skeleton, 53),
]

CLUT_WIDTH = 16
BLOCK_WIDTH = 64
TEXTURE_WIDTH = 0x100
TEXTURE_HEIGHT = 0x100
VERT_SIZE = 3 * 4
UV_SIZE = 2 * 4


class Model(FileFormat):
    """A 3D model of a game object"""

    def __init__(self, attributes: list[Vertex], root_segments: list[Segment],
                 all_segments: list[Segment], texture: Tim, use_transparency: bool = False, anim_index: int = None,
                 scale: int = None):
        self.attributes = attributes
        self.root_segments = root_segments
        self.all_segments = all_segments
        self.texture = texture
        self.use_transparency = use_transparency
        self.anim_index = anim_index
        self.scale = scale
        self.animations = None

    def set_animations(self, animations: AnimationDb | None):
        self.animations = animations

    @property
    def panda_scale(self) -> float:
        return 1. if self.scale is None else self.scale / 100

    @property
    @abstractmethod
    def suggested_extension(self) -> str:
        pass

    @functools.cache
    def get_panda3d_model(self) -> NodePath:
        vdata = GeomVertexData('', GeomVertexFormat.getV3n3t2(), Geom.UHStatic)
        vdata.setNumRows(len(self.attributes))

        vertex = GeomVertexWriter(vdata, 'vertex')
        normal = GeomVertexWriter(vdata, 'normal')
        texcoord = GeomVertexWriter(vdata, 'texcoord')

        tex_height = self.texture_height
        for vert in self.attributes:
            point = Point(vert.x, vert.y, vert.z)
            # by this point all vertices should have normals because we should've calculated them for the ones that
            # didn't have them
            norm = vert.normal
            vertex.addData3(point.panda_x, point.panda_y, point.panda_z)
            normal.addData3(norm[0], norm[1], norm[2])
            texcoord.addData2(vert.u / TEXTURE_WIDTH, (tex_height - vert.v) / tex_height)

        node_path = NodePath(PandaNode('model_root'))
        for segment in self.root_segments:
            child_path = segment.as_node_path(vdata)
            child_path.reparentTo(node_path)

        if self.scale is not None:
            node_path.setScale(self.panda_scale)

        return node_path

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

    def _set_segment_panda_translation(self, segment_index: int, translation: Point, node_path: NodePath) -> bool:
        name: str = node_path.getName()
        if name == f'segment{segment_index}':
            node_path.setPos(translation.panda_x, translation.panda_y, translation.panda_z)
            return True

        for child in node_path.getChildren():
            if self._set_segment_panda_translation(segment_index, translation, child):
                return True

        return False

    def set_segment_translation(self, segment_index: int, x: int = None, y: int = None, z: int = None) -> bool:
        """
        Set the translation of one of the model's segment, including updating the Panda3D model

        Any axes that aren't provided (i.e. set to None) will retain their original values.

        :param segment_index: The index of the segment whose translation to set
        :param x: The new x translation
        :param y: The new y translation
        :param z: The new z translation
        :return: True if the translation was changed, False if the new translation was identical to the old translation
        """
        segment = self.all_segments[segment_index]

        old_x, old_y, old_z = segment.offset
        new_offset = (old_x if x is None else x, old_y if y is None else y, old_z if z is None else z)
        if new_offset == segment.offset:
            return False

        if not segment.can_change_translation:
            raise ValueError(f'Translation of segment {segment_index} cannot be changed')

        segment.offset = new_offset
        self._set_segment_panda_translation(segment_index, Point(*new_offset), self.get_panda3d_model())
        return True

    def focus_segment(self, index: int, node_path: NodePath = None, focus_alpha: float = 1., unfocus_alpha: float = 0.5):
        """
        Make all segments except for the focused segment transparent

        :param index: The index of the segment to focus
        :param node_path: For internal use only
        :param focus_alpha: For internal use only
        :param unfocus_alpha: For internal use only
        """

        if node_path is None:
            node_path = self.get_panda3d_model()

        name: str = node_path.getName()
        if name != f'segment{index}':
            node_path.setColorScale(1., 1., 1., unfocus_alpha)
            new_unfocus_alpha = 1.  # just keep alpha from the parent
            new_focus_alpha = focus_alpha / unfocus_alpha  # scale back to the desired value
        else:
            node_path.setColorScale(1., 1., 1., focus_alpha)
            new_unfocus_alpha = 0.5  # any children of the focused segment need the alpha reapplied
            new_focus_alpha = focus_alpha  # we shouldn't need this again, so just keep the old value

        for child in node_path.getChildren():
            self.focus_segment(index, child, new_focus_alpha, new_unfocus_alpha)

    def unfocus(self, node_path: NodePath = None):
        """
        Clear any focus effect set with focus_segment
        """
        if node_path is None:
            node_path = self.get_panda3d_model()

        node_path.clearColorScale()
        for child in node_path.getChildren():
            self.unfocus(child)

    @property
    def texture_height(self) -> int:
        return TEXTURE_HEIGHT * self.texture.num_palettes

    def _flatten(self) -> tuple[list[tuple[int, int, int]], list[Vertex]]:
        new_tris = []
        new_attributes = {}
        for segment in self.root_segments:
            new_tris.extend(segment.flatten(new_attributes, self.attributes))
        return new_tris, list(new_attributes)

    @classmethod
    def _gltf_add_segment(cls, gltf: dict[str, Any], root_node: dict[str, str | list[int]],
                          buffer: bytearray, segment: Segment, node_map: dict[int, int], view_start: int = 0):
        byte_offset = len(buffer)
        index_count = 0
        max_index = 0
        min_index = None
        for tri in segment.all_triangles:
            # glTF uses counter-clockwise winding order
            buffer += struct.pack('<3H', tri[0], tri[2], tri[1])
            new_max = max(tri)
            if new_max > max_index:
                max_index = new_max
            new_min = min(tri)
            if min_index is None or new_min < min_index:
                min_index = new_min
            index_count += 3
        node_index = len(gltf['nodes'])
        root_node['children'].append(node_index)
        node_map[segment.index] = node_index
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
            'byteOffset': byte_offset - view_start,
            'componentType': Gltf.UNSIGNED_SHORT,
            'count': index_count,
            'type': 'SCALAR',
            'max': [max_index],
            'min': [min_index or 0],
        })
        gltf['meshes'].append({
            'primitives': [
                {
                    'attributes': {
                        'POSITION': 0,
                        'NORMAL': 1,
                        'TEXCOORD_0': 2,
                    },
                    'indices': index_accessor,
                    'material': 0,
                },
            ],
        })

        for child in segment.children:
            cls._gltf_add_segment(gltf, node, buffer, child, node_map, view_start)

    def as_gltf(self) -> tuple[dict[str, Any], bytes, Image.Image]:
        # * 2 for position + normal
        stride = VERT_SIZE * 2 + UV_SIZE
        num_attrs = len(self.attributes)
        buffer = bytearray(num_attrs * stride)
        buf_len = 0
        tex_height = self.texture_height
        inf = float('inf')
        minf = float('-inf')
        max_x = max_y = max_z = max_u = max_v = max_nx = max_ny = max_nz = minf
        min_x = min_y = min_z = min_u = min_v = min_nx = min_ny = min_nz = inf
        for vert in self.attributes:
            x = vert.x / Dimension.SCALE_FACTOR
            min_x = min(x, min_x)
            max_x = max(x, max_x)

            y = vert.y / Dimension.SCALE_FACTOR
            min_y = min(y, min_y)
            max_y = max(y, max_y)

            z = vert.z / Dimension.SCALE_FACTOR
            min_z = min(z, min_z)
            max_z = max(z, max_z)

            u = vert.u / TEXTURE_WIDTH
            min_u = min(u, min_u)
            max_u = max(u, max_u)

            v = vert.v / tex_height
            min_v = min(v, min_v)
            max_v = max(v, max_v)

            normal = -vert.normal

            nx = -normal[0]
            min_nx = min(nx, min_nx)
            max_nx = max(nx, max_nx)

            ny = normal[2]
            min_ny = min(ny, min_ny)
            max_ny = max(ny, max_ny)

            nz = normal[1]
            min_nz = min(nz, min_nz)
            max_nz = max(nz, max_nz)

            struct.pack_into('<8f', buffer, buf_len, x, y, z, nx, ny, nz, u, v)
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
            'animations': [],
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
                    'name': 'attributes',
                    'buffer': 0,
                    'byteOffset': 0,
                    'byteLength': buf_len,
                    'byteStride': stride,
                    'target': Gltf.ARRAY_BUFFER,
                },
                {
                    'name': 'indices',
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
                    'name': 'normals',
                    'bufferView': 0,
                    'byteOffset': VERT_SIZE,
                    'componentType': Gltf.FLOAT,
                    'count': num_attrs,
                    'type': 'VEC3',
                    'min': [min_nx, min_ny, min_nz],
                    'max': [max_nx, max_ny, max_nz],
                },
                {
                    'name': 'texcoords',
                    'bufferView': 0,
                    'byteOffset': VERT_SIZE * 2,
                    'componentType': Gltf.FLOAT,
                    'count': num_attrs,
                    'type': 'VEC2',
                    'min': [min_u, min_v],
                    'max': [max_u, max_v],
                },
            ],
        }

        root_node = gltf['nodes'][0]
        view_start = len(buffer)
        node_map = {}
        for root_segment in self.root_segments:
            self._gltf_add_segment(gltf, root_node, buffer, root_segment, node_map, view_start)

        # accessor byte offsets must be a multiple of the data type size
        if bytes_over := len(buffer) % 4:
            buffer += bytes(4 - bytes_over)
        len_after_index = len(buffer)
        gltf['bufferViews'][1]['byteLength'] = len_after_index - buf_len

        if self.animations:
            # animation samplers can't use buffer views with a byte stride, so we need each segment's rotations to
            # go into their own section of the buffer
            num_segs = 15
            rot_bufs = [bytearray() for _ in range(num_segs)]

            # generate timestamps
            max_frames = max(len(animation.frames) for animation in self.animations if animation)
            timestamps = [Animation.FRAME_TIME * i for i in range(max_frames)]
            buffer += struct.pack(f'<{max_frames}f', *timestamps)
            len_after_timestamps = len(buffer)
            # buffer views for animation data do not have a target property
            gltf['bufferViews'].extend([
                {
                    'name': 'timestamps',
                    'buffer': 0,
                    'byteOffset': len_after_index,
                    'byteLength': len_after_timestamps - len_after_index,
                },
                {
                    'name': 'translations',
                    'buffer': 0,
                    'byteOffset': len_after_timestamps,
                    'byteLength': 0,
                },
            ])
            prev_len = len_after_timestamps
            first_rot_view = len(gltf['bufferViews'])
            for i in range(len(rot_bufs)):
                gltf['bufferViews'].append({
                    'name': f'rotations_{i}',
                    'buffer': 0,
                    'byteOffset': 0,
                    'byteLength': 0,
                })

            for i, animation in enumerate(self.animations):
                if animation:
                    start_len = len(buffer)
                    rot_starts = [len(rot_buf) for rot_buf in rot_bufs]
                    trans_min = np.array([inf, inf, inf], np.float32)
                    trans_max = np.array([minf, minf, minf], np.float32)
                    rotation_extrema = [(np.array([inf, inf, inf, inf], np.float32),
                                         np.array([minf, minf, minf, minf], np.float32))
                                        for _ in range(num_segs)]
                    for j in range(len(animation.frames)):
                        translation, rotations = animation.convert_frame(j)
                        trans_min = np.minimum(translation, trans_min)
                        trans_max = np.maximum(translation, trans_max)
                        buffer += translation.tobytes()
                        for k, rotation in enumerate(rotations[:num_segs]):
                            # convert to quaternion
                            half_rads = rotation / 2
                            cx, cy, cz = np.cos(half_rads)
                            sx, sy, sz = np.sin(half_rads)
                            qx = np.array([sx, 0., 0., cx], np.float32)
                            qy = np.array([0., sy, 0., cy], np.float32)
                            qz = np.array([0., 0., sz, cz], np.float32)
                            quaternion = graphics.quat_mul(qx, graphics.quat_mul(qy, qz))
                            norm = np.linalg.norm(quaternion)
                            if norm != 0:
                                quaternion /= norm
                            mins, maxes = rotation_extrema[k]
                            mins = np.minimum(quaternion, mins)
                            maxes = np.maximum(quaternion, maxes)
                            rotation_extrema[k] = (mins, maxes)
                            rot_bufs[k] += quaternion.tobytes()

                    num_frames = len(animation.frames)
                    timestamp_accessor = len(gltf['accessors'])
                    gltf['accessors'].append({
                        'name': f'timestamps_{i}',
                        'bufferView': 2,
                        'byteOffset': 0,
                        'componentType': Gltf.FLOAT,
                        'count': num_frames,
                        'type': 'SCALAR',
                        'min': [0.],
                        'max': [timestamps[num_frames - 1]],
                    })
                    translation_accessor = len(gltf['accessors'])
                    gltf['accessors'].append({
                        'name': f'translation_{i}',
                        'bufferView': 3,
                        'byteOffset': start_len - prev_len,
                        'componentType': Gltf.FLOAT,
                        'count': num_frames,
                        'type': 'VEC3',
                        'min': trans_min.tolist(),
                        'max': trans_max.tolist(),
                    })

                    channels = [
                        {
                            'sampler': 0,
                            'target': {
                                'node': 0,
                                'path': 'translation',
                            },
                        },
                    ]
                    samplers = [{'input': timestamp_accessor, 'output': translation_accessor}]
                    for k in range(num_segs):
                        rotation_accessor = len(gltf['accessors'])
                        gltf['accessors'].append({
                            'name': f'rotation_{i}_{k}',
                            'bufferView': first_rot_view + k,
                            'byteOffset': rot_starts[k],
                            'componentType': Gltf.FLOAT,
                            'count': num_frames,
                            'type': 'VEC4',
                            'min': rotation_extrema[k][0].tolist(),
                            'max': rotation_extrema[k][1].tolist(),
                        })

                        sampler = len(samplers)
                        samplers.append({'input': timestamp_accessor, 'output': rotation_accessor})
                        channels.append({
                            'sampler': sampler,
                            'target': {
                                'node': node_map[k],
                                'path': 'rotation',
                            },
                        })

                    gltf['animations'].append({
                        'name': f'{i}',
                        'channels': channels,
                        'samplers': samplers,
                    })

            # append rotation buffers and update views
            len_after_translations = len(buffer)
            gltf['bufferViews'][3]['byteLength'] = len_after_translations - prev_len
            prev_len = len_after_translations
            for i, rot_buf in enumerate(rot_bufs):
                index = first_rot_view + i
                gltf['bufferViews'][index]['byteOffset'] = prev_len
                gltf['bufferViews'][index]['byteLength'] = len(rot_buf)
                buffer += rot_buf
                prev_len = len(buffer)

        final_buf = bytes(buffer)
        final_len = len(final_buf)
        gltf['buffers'][0]['byteLength'] = final_len

        # empty children arrays not allowed per spec
        for node in gltf['nodes']:
            if not node['children']:
                del node['children']

        return gltf, final_buf, self.get_texture_image()

    def as_glb(self) -> bytes:
        glb = bytearray()
        gltf, buffer, texture = self.as_gltf()

        # GLB only allows a single buffer, so we need to pack the texture into the buffer
        tex_offset = len(buffer)
        with io.BytesIO() as tex_bin:
            texture.save(tex_bin, format='png')
            buffer += tex_bin.getvalue()
        buffer_size = len(buffer)
        tex_size = buffer_size - tex_offset
        # update buffers and images accordingly
        del gltf['buffers'][0]['uri']
        gltf['buffers'][0]['byteLength'] = buffer_size
        tex_buffer_view = len(gltf['bufferViews'])
        gltf['bufferViews'].append({
            'name': 'texture',
            'buffer': 0,
            'byteOffset': tex_offset,
            'byteLength': tex_size,
        })
        gltf['images'][0] = {'bufferView': tex_buffer_view, 'mimeType': 'image/png'}

        glb += Glb.MAGIC.to_bytes(4, 'little')
        # this is a 4-byte field; the extra 4 bytes are a placeholder for the length
        glb += Glb.VERSION.to_bytes(8, 'little')

        # JSON chunk
        json_bin = json.dumps(gltf).encode()
        if bytes_over := len(json_bin) % 4:
            json_bin += b' ' * (4 - bytes_over)
        glb += len(json_bin).to_bytes(4, 'little')
        glb += Glb.JSON.to_bytes(4, 'little')
        glb += json_bin

        # BIN chunk
        if bytes_over := buffer_size % 4:
            buffer += bytes(4 - bytes_over)
        glb += len(buffer).to_bytes(4, 'little')
        glb += Glb.BIN.to_bytes(4, 'little')
        glb += buffer

        # update length
        glb[8:12] = len(glb).to_bytes(4, 'little')

        return bytes(glb)

    def as_ply(self) -> str:
        tris, attributes = self._flatten()
        ply = f"""ply
format ascii 1.0
element vertex {len(attributes)}
property float x
property float y
property float z
property float nx
property float ny
property float nz
property float s
property float t
element face {len(tris)}
property list uchar uint vertex_indices
end_header
"""
        for v in attributes:
            point = Point(v.x, v.y, v.z)
            normal = v.normal
            s = v.u / TEXTURE_WIDTH
            t = 1. - (v.v / self.texture_height)
            ply += f'{point.panda_x} {point.panda_y} {point.panda_z} {normal[0]} {normal[1]} {normal[2]} {s} {t}\n'
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
            # OBJ format uses the same coordinate system as the PlayStation, so we don't want to do the usual
            # coordinate transformation here. we still need to flip the normal vector, though
            obj += (
                f'v {v.x / Dimension.SCALE_FACTOR} {v.y / Dimension.SCALE_FACTOR} {v.z / Dimension.SCALE_FACTOR}\n'
                f'vt {v.u / TEXTURE_WIDTH} {(tex_height - v.v) / tex_height}\n'
                f'vn {-v.nx / 4096} {-v.ny / 4096} {-v.nz / 4096}\n'
            )
        if material_name is not None:
            obj += f'usemtl {material_name}\n'
        for t in tris:
            v1 = t[0] + 1
            v2 = t[1] + 1
            v3 = t[2] + 1
            obj += f'f {v1}/{v1}/{v1} {v3}/{v3}/{v3} {v2}/{v2}/{v2}\n'

        if material_name is not None:
            mtl = f"""newmtl {material_name}
Ka 1.000 1.000 1.000
Kd 1.000 1.000 1.000
Ks 0.000 0.000 0.000
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
                model.setTexture(texture)
                model.writeBamFile(file.panda_path(new_path))
            case 'gltf':
                new_path = path.with_suffix('.gltf')
                texture_path = path.with_suffix('.png')
                bin_path = path.with_suffix('.bin')
                gltf, buffer, texture = self.as_gltf()
                gltf['images'][0]['uri'] = texture_path.name
                gltf['buffers'][0]['uri'] = bin_path.name
                with new_path.open('w') as f:
                    json.dump(gltf, f, indent=4)
                texture.save(texture_path)
                bin_path.write_bytes(buffer)
            case 'glb':
                new_path = path.with_suffix('.glb')
                new_path.write_bytes(self.as_glb())
            case 'tim':
                new_path = path.with_suffix('.tim')
                with new_path.open('wb') as f:
                    self.texture.write(f)
            case _:
                raise ValueError(f'Unknown format {fmt}')

        return new_path

    def write(self, f: BinaryIO, **kwargs):
        raise NotImplementedError

    def get_texture_image(self) -> Image.Image:
        if self.use_transparency:
            transparent_palettes = {segment.clut_index for segment in self.all_segments if segment.has_transparency}
        else:
            transparent_palettes = set()
        image = Image.new('RGBA', (TEXTURE_WIDTH, self.texture_height))
        for i in range(self.texture.num_palettes):
            transparency = Transparency.SEMI if i in transparent_palettes else Transparency.NONE
            sub_image = self.texture.to_image(i, transparency)
            image.paste(sub_image, (0, TEXTURE_HEIGHT * i))
        return image

    def get_true_color_texture_image(self) -> Image.Image:
        image = Image.new('RGBA', (TEXTURE_WIDTH, TEXTURE_HEIGHT))
        stacked_image = self.get_texture_image()
        # initially fill the final image in with the first palette just to make sure we have a value for every pixel
        image.paste(stacked_image.crop((0, 0, TEXTURE_WIDTH, TEXTURE_HEIGHT)), (0, 0))

        for segment in self.all_segments:
            mask = Image.new('L', (TEXTURE_WIDTH, TEXTURE_HEIGHT))
            draw = ImageDraw.Draw(mask)
            for tri in segment.all_triangles:
                v1 = self.attributes[tri[0]]
                v2 = self.attributes[tri[1]]
                v3 = self.attributes[tri[2]]

                poly = [
                    (v1.u, v1.v % TEXTURE_HEIGHT),
                    (v2.u, v2.v % TEXTURE_HEIGHT),
                    (v3.u, v3.v % TEXTURE_HEIGHT),
                ]

                # don't copy pixels for polygons with zero area
                area = abs(poly[0][0] * (poly[1][1] - poly[2][1]) + poly[1][0] * (poly[2][1] - poly[0][1]) +
                           poly[2][0] * (poly[0][1] - poly[1][1])) / 2
                if area > 0:
                    draw.polygon(poly, fill=255)

            image.paste(stacked_image.crop((0, segment.clut_index * TEXTURE_HEIGHT, TEXTURE_WIDTH, (segment.clut_index + 1) * TEXTURE_HEIGHT)), None, mask)

        return image

    @staticmethod
    def _set_tri_normals(vertices: list[Vertex]):
        if not vertices:
            return

        # calculate surface normals for flat shading
        v1 = np.array([Point(vert.x, vert.y, vert.z).ndarray for vert in vertices[::3]])
        v2 = np.array([Point(vert.x, vert.y, vert.z).ndarray for vert in vertices[1::3]])
        v3 = np.array([Point(vert.x, vert.y, vert.z).ndarray for vert in vertices[2::3]])
        # we won't normalize yet, we'll do that together with the game's own normals later
        normals = np.cross(v2 - v1, v3 - v1)
        for i, normal in enumerate(normals):
            # flip the vector for consistency with the game's own normals
            point = Point.from_ndarray(-normal)
            for j in range(3):
                index = i * 3 + j
                vert = vertices[index]
                vertices[index] = vert.with_normal(point.game_x, point.game_y, point.game_z, False)

    @staticmethod
    def _set_quad_normals(vertices: list[Vertex]):
        if not vertices:
            return

        # calculate surface normals for flat shading
        v1 = np.array([Point(vert.x, vert.y, vert.z).ndarray for vert in vertices[::4]])
        v2 = np.array([Point(vert.x, vert.y, vert.z).ndarray for vert in vertices[1::4]])
        v3 = np.array([Point(vert.x, vert.y, vert.z).ndarray for vert in vertices[2::4]])
        v4 = np.array([Point(vert.x, vert.y, vert.z).ndarray for vert in vertices[3::4]])
        normals1 = np.cross(v2 - v1, v3 - v1)
        normals2 = np.cross(v4 - v3, v1 - v3)
        # we won't normalize yet, we'll do that together with the game's own normals later
        normals = normals1 + normals2
        for i, normal in enumerate(normals):
            # flip the vector for consistency with the game's own normals
            point = Point.from_ndarray(-normal)
            for j in range(4):
                index = i * 4 + j
                vert = vertices[index]
                vertices[index] = vert.with_normal(point.game_x, point.game_y, point.game_z, False)

    @staticmethod
    def _read_chunk(f: BinaryIO, num_vertices: int, has_normals: bool = False) -> list[Vertex]:
        num_shorts = num_vertices * 3
        num_bytes = num_vertices * 2
        num_normal_shorts = num_shorts if has_normals else 0
        data_size = (num_shorts + num_normal_shorts) * 2 + num_bytes
        count = file.int_from_bytes(f.read(2))
        attributes = []
        fmt = f'<{num_shorts}h{num_bytes}B'
        if has_normals:
            fmt += f'{num_normal_shorts}h'
        for k in range(count):
            data = f.read(data_size)
            raw_face = struct.unpack(fmt, data)
            for m in range(num_vertices):
                x, y, z = raw_face[m * 3:(m + 1) * 3]
                attributes.append(Vertex(x, y, z, 0, 0))
            rest = raw_face[num_shorts:]
            for m in range(num_vertices):
                u = rest[m * 2]
                v = rest[m * 2 + 1]
                attr_index = m + k * num_vertices
                attr = attributes[attr_index]
                attributes[attr_index] = attr.with_uv(u, v)
            if has_normals:
                rest = rest[num_bytes:]
                for m in range(num_vertices):
                    nx, ny, nz = rest[m * 3:(m + 1) * 3]
                    attr_index = m + k * num_vertices
                    attr = attributes[attr_index]
                    attributes[attr_index] = attr.with_normal(nx, ny, nz)

        return attributes

    @staticmethod
    def _write_chunk(f: BinaryIO, polygons: list[Sequence[Vertex]], has_normals: bool = False):
        num_polygons = len(polygons)
        f.write(num_polygons.to_bytes(2, 'little'))
        if num_polygons == 0:
            return

        for polygon in polygons:
            for vertex in polygon:
                f.write(struct.pack('<3h', vertex.x, vertex.y, vertex.z))
            for vertex in polygon:
                f.write(struct.pack('<2B', vertex.u, vertex.v % TEXTURE_HEIGHT))
            if has_normals:
                for vertex in polygon:
                    f.write(struct.pack('<3h', vertex.nx, vertex.ny, vertex.nz))

    @staticmethod
    def _read_tim(f: BinaryIO) -> Tim:
        texture = f.read(0x8000)
        clut = f.read(0x80)

        tim = Tim()
        tim.set_clut(clut, CLUT_WIDTH)
        tim.set_image(texture, BitsPerPixel.BPP_4, BLOCK_WIDTH)
        assert tim.num_palettes == 4

        return tim

    def _write_tim(self, f: BinaryIO):
        f.write(self.texture.image_data)
        f.write(self.texture.clut_data)

    def _write_segment(self, f: BinaryIO, segment: Segment):
        f.write(segment.clut_index.to_bytes(2, 'little'))
        triangles = [[self.attributes[i] for i in triangle] for triangle in segment.triangles]
        quads = [[self.attributes[i] for i in quad] for quad in segment.quads]
        # split into flat-shaded vs gouraud-shaded groups
        gouraud_tris = [poly for poly in triangles if all(vert.has_original_normals for vert in poly)]
        flat_tris = [poly for poly in triangles if any(not vert.has_original_normals for vert in poly)]

        gouraud_quads = [poly for poly in quads if all(vert.has_original_normals for vert in poly)]
        flat_quads = [poly for poly in quads if any(not vert.has_original_normals for vert in poly)]

        self._write_chunk(f, flat_quads)
        self._write_chunk(f, flat_tris)
        self._write_chunk(f, gouraud_quads, True)
        self._write_chunk(f, gouraud_tris, True)

    @classmethod
    def _read_segment(cls, f: BinaryIO, index: int, attributes: dict[Vertex, int],
                      offset: tuple[int, int, int] = (0, 0, 0), can_change_translation: bool = False,
                      file_index: int = None, has_transparency: bool = False) -> Segment:
        clut_index = int.from_bytes(f.read(2), 'little')
        tri_attrs = []
        quad_attrs = []

        # flat-shaded polygons
        quad_attrs.extend(cls._read_chunk(f, 4))
        cls._set_quad_normals(quad_attrs)
        tri_attrs.extend(cls._read_chunk(f, 3))
        cls._set_tri_normals(tri_attrs)

        # gouraud-shaded polygons
        quad_attrs.extend(cls._read_chunk(f, 4, True))
        tri_attrs.extend(cls._read_chunk(f, 3, True))

        tri_attrs_final, quad_attrs_final = ([
            attributes.setdefault(replace(vert, v=vert.v + TEXTURE_HEIGHT * clut_index), len(attributes))
            for vert in attrs
        ] for attrs in [tri_attrs, quad_attrs])

        triangles = [
            (tri_attrs_final[i], tri_attrs_final[i + 1], tri_attrs_final[i + 2]) for i in range(0, len(tri_attrs), 3)
        ]
        quads = [
            (quad_attrs_final[i], quad_attrs_final[i + 1], quad_attrs_final[i + 2], quad_attrs_final[i + 3])
            for i in range(0, len(quad_attrs), 4)
        ]

        return Segment(index, clut_index, triangles, quads, offset, can_change_translation=can_change_translation,
                       file_index=index if file_index is None else file_index, has_transparency=has_transparency)


class ActorModel(Model):
    """A 3D model of an actor (character)"""

    NUM_SEGMENTS = 19
    SEGMENT_ORDER = [0, 1, 2, 3, 4, 6, 7, 9, 10, 11, 12, 13, 14, 5, 15, 16, 8, 17, 18]

    def __init__(self, name: str, actor_id: int, attributes: list[Vertex], root: Segment, all_segments: list[Segment],
                 texture: Tim, anim_index: int = None):
        super().__init__(attributes, [root], all_segments, texture, anim_index=anim_index)
        self.name = name
        self.id = actor_id

    @property
    def suggested_extension(self) -> str:
        return '.G3A'

    @classmethod
    def add_segment(cls, root: Segment, segments: list[Segment], skeleton: dict[int, dict]):
        for index, sub_skeleton in skeleton.items():
            child = root.add_child(segments[index])
            cls.add_segment(child, segments, sub_skeleton)

    @classmethod
    def read(cls, f: BinaryIO, *, actor: Actor = None, anim_index: int = None, **kwargs) -> ActorModel:
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
        for j, i in enumerate(cls.SEGMENT_ORDER):
            try:
                offset = (offsets[i * 3], offsets[i * 3 + 1], offsets[i * 3 + 2])
                can_change_translation = True
            except IndexError:
                offset = (0, 0, 0)
                can_change_translation = False
            segment = cls._read_segment(f, i, attributes, offset, can_change_translation, j)
            segments[i] = segment

        root = segments[0]
        cls.add_segment(root, segments, actor.skeleton[0])
        if actor.id == DOROTHY_EYE.id:
            # something special must be going on in the code for this model, because it just adds segments 0 through 7,
            # but here it doesn't seem to look right unless we put 5 after 6 and remove the vertical offset on 7
            offset = segments[7].offset
            segments[7].offset = (offset[0], 0, offset[2])

        return cls(actor.name, actor.id, list(attributes), root, segments, tim, anim_index)

    def write(self, f: BinaryIO, **kwargs):
        all_offsets = [o for segment in self.all_segments for o in segment.offset]
        f.write(struct.pack('<46h', *all_offsets[:46]))
        self._write_tim(f)

        for segment in sorted(self.all_segments, key=lambda s: s.file_index):
            self._write_segment(f, segment)


class ItemModel(Model):
    """A 3D model of an item"""

    MAX_SEGMENTS = 19

    def __init__(self, name: str, attributes: list[Vertex], segments: list[Segment], texture: Tim,
                 use_transparency: bool = False, scale: int = None):
        super().__init__(attributes, segments, segments, texture, use_transparency)
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
             num_segments: int = None, transparent_segments: Container[int] = None, scale: int = None,
             **kwargs) -> ItemModel:
        if transparent_segments:
            use_transparency = True
        else:
            transparent_segments = []

        tim = cls._read_tim(f)

        attributes = {}
        segments = []
        for i in range(cls.MAX_SEGMENTS if num_segments is None else num_segments):
            try:
                segments.append(cls._read_segment(f, i, attributes, has_transparency=i in transparent_segments))
            except ValueError:
                # MODEL.CDB 92 and 93 fail to load with this enabled, but it's appropriate for sniffing
                # if num_segments is set,
                if strict_mode or num_segments is not None:
                    raise
                break
            except struct.error:
                break
        return cls(name, list(attributes), segments, tim, use_transparency, scale)

    def write(self, f: BinaryIO, **kwargs):
        self._write_tim(f)
        for segment in self.all_segments:
            self._write_segment(f, segment)


def export(model_path: str, target_path: str, animation_path: str | None, actor_id: int | None, differential: bool,
           true_color: bool):
    model_path = Path(model_path)
    target_path = Path(target_path)
    with model_path.open('rb') as f:
        if actor_id is None:
            model = ItemModel.read(f)
        else:
            actors = ACTORS if differential else ZANMAI_ACTORS
            actors_by_id = {actor.id: actor for actor in actors}
            model = ActorModel.read(f, actor=actors_by_id.get(actor_id, actors[0]))
    if animation_path:
        with open(animation_path, 'rb') as f:
            db = AnimationDb.read(f, differential=differential)
        model.set_animations(db)

    if target_path.suffix.lower() == '.png':
        if true_color:
            model.get_true_color_texture_image().save(target_path)
        else:
            model.get_texture_image().save(target_path)
    else:
        model.export(target_path, target_path.suffix)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Export Galerians 3D models and textures')
    parser.add_argument('-a', '--actor', type=int, help='The given model file is an actor model. The argument should '
                        'be the ID of the actor the model belongs to.')
    parser.add_argument('-m', '--animation', help='Path to an animation database to include in the export. Ignored '
                        'if not exporting as gltf or glb.')
    parser.add_argument('-u', '--uncompressed', help="The provided animation database doesn't use differential "
                        'compression. Only use this with animations from the ASCII Zanmai demo disc.',
                        action='store_true')
    parser.add_argument('-t', '--true-color', help='When exporting the texture to PNG, attempt to use the '
                        'model UVs to identify the correct palette for each pixel and output a full-color 256x256 image '
                        'instead of stacking the palettes into a 256x1024 image.',
                        action='store_true')
    parser.add_argument('model', help='The model file to be exported')
    parser.add_argument('target', help='The path to export the model to. The format will be detected from the file '
                        'extension. Supported extensions are ply, obj, gltf, glb, and bam for model data. The texture '
                        'can also be exported with extensions tim or png. When exporting to PNG, by default the '
                        'image will contain each of the palettes in the texture stacked vertically for a 256x1024 image. '
                        'Use the --true-color option to attempt to use the model UVs to identify the correct palette '
                        'for each pixel and output a single full-color 256x256 image instead.')

    args = parser.parse_args()
    export(args.model, args.target, args.animation, args.actor, not args.uncompressed, args.true_color)
