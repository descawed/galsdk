from __future__ import annotations

import struct
from dataclasses import astuple, dataclass
from enum import IntEnum
from pathlib import Path
from typing import BinaryIO, Self, Iterable

from PIL import Image

from galsdk.format import FileFormat
from galsdk.util import int_from_bytes
from psx.tim import BitsPerPixel, Tim


class MenuElement(IntEnum):
    PRE_END = 1
    END = 2
    IMAGE = 3
    CLUT_INFO = 4
    COMPONENT = 5
    TILE = 6
    CLUT_DATA = 7
    LAYOUT = 14


@dataclass
class MenuImage:
    width: int
    height: int
    data: bytes


@dataclass
class ClutInfo:
    unused: int
    image_index: int
    x: int
    y: int

    @property
    def is_embedded(self) -> bool:
        return self.image_index != 128


@dataclass
class Component:
    unused: int
    x: int
    y: int
    start_index: int
    stop_index: int
    unknown6: int
    unknown7: int
    unknown8: int
    unknown9: int
    unknown10: int
    unknown11: int


@dataclass
class Tile:
    width: int
    height: int
    layouts: tuple[int, int, int, int]
    x_scale_index: int
    image_index: int
    x_offset: int
    y_offset: int
    clut_index: int
    unused: int
    unknown: int


@dataclass
class Layout:
    x: int
    y: int


@dataclass
class ComponentInstance:
    x: int
    y: int
    component_index: int
    rgb: tuple[int, int, int]
    draw: int = 0


class Menu(FileFormat):
    def __init__(self, images: list[MenuImage], clut_settings: list[ClutInfo], components: list[Component],
                 tiles: list[Tile], clut_data: list[bytes], layouts: list[Layout], x_scales: list[int] = None,
                 instances: list[ComponentInstance] = None, unused: int = 0):
        self.unused = unused
        self.images = images
        self.clut_settings = clut_settings
        self.components = components
        self.tiles = tiles
        self.clut_data = clut_data
        self.layouts = layouts
        self.x_scales = x_scales or [4, 2, 1]
        self.instances = instances

    def instantiate(self, instances: list[ComponentInstance], x_scales: list[int]):
        self.x_scales = x_scales
        self.instances = instances

    def render(self, layout_index: int = 0) -> Image.Image:
        if not self.instances:
            raise NotImplementedError('Menu layout is not known')

        image = Image.new('RGBA', (320, 240), (0, 0, 0, 255))
        for instance in self.instances:
            component = self.components[instance.component_index]
            for tile_index in range(component.start_index, component.stop_index):
                layout = self.layouts[self.tiles[tile_index].layouts[layout_index]]
                tile = self[tile_index]
                image.alpha_composite(tile,
                                      (instance.x + component.x + layout.x, instance.y + component.y + layout.y))

        return image

    def __getitem__(self, item: int) -> Image.Image:
        tile_info = self.tiles[item]
        x = tile_info.x_offset * self.x_scales[tile_info.x_scale_index]
        y = tile_info.y_offset & 0xff
        image = self.images[tile_info.image_index]
        clut_info = self.clut_settings[tile_info.clut_index]
        tim = Tim()
        if clut_info.is_embedded:
            clut_image = self.images[clut_info.image_index]
            clut_offset = 2 * (clut_image.width * clut_info.y + clut_info.x)
            clut = clut_image.data[clut_offset:clut_offset + 32]
            tim.set_clut(clut, len(clut) // 2)
            tim.set_image(image.data, BitsPerPixel.BPP_4, image.width)
        else:
            clut = self.clut_data[clut_info.x]
            tim.set_clut(clut, len(clut) // 2)
            tim.set_image(image.data, BitsPerPixel.BPP_8, image.width)
        image = tim.to_image().crop((x, y, x + tile_info.width, y + tile_info.height))
        return image

    def __iter__(self) -> Iterable[Image.Image]:
        for i in range(len(self.tiles)):
            yield self[i]

    def __len__(self) -> int:
        return len(self.tiles)

    def unpack_one(self, path: Path, index: int) -> Path:
        self[index].save(path)
        return path

    @property
    def suggested_extension(self) -> str:
        return '.MNU'

    @classmethod
    def read(cls, f: BinaryIO, **kwargs) -> Self:
        images = []
        clut_settings = []
        components = []
        tiles = []
        clut_data = []
        layouts = []

        unused = int_from_bytes(f.read(4))
        while True:
            element_type = MenuElement(int_from_bytes(f.read(2)))
            match element_type:
                case MenuElement.PRE_END:
                    pass
                case MenuElement.END:
                    break
                case MenuElement.IMAGE:
                    count = int_from_bytes(f.read(2))
                    for _ in range(count):
                        width = int_from_bytes(f.read(2))
                        height = int_from_bytes(f.read(2))
                        data = f.read(2 * width * height)
                        images.append(MenuImage(width, height, data))
                case MenuElement.CLUT_INFO:
                    count = int_from_bytes(f.read(2))
                    for _ in range(count):
                        clut_settings.append(ClutInfo(*f.read(4)))
                case MenuElement.COMPONENT:
                    count = int_from_bytes(f.read(2))
                    for _ in range(count):
                        components.append(Component(*struct.unpack('<11H', f.read(22))))
                case MenuElement.TILE:
                    count = int_from_bytes(f.read(2))
                    for _ in range(count):
                        width, height, layout1, layout2, layout3, layout4, x_scale_index, image_index, x_offset, \
                            y_offset, clut_index, unused, unknown = struct.unpack('<6H6BH', f.read(20))
                        tiles.append(Tile(width, height, (layout1, layout2, layout3, layout4), x_scale_index,
                                          image_index, x_offset, y_offset, clut_index, unused, unknown))
                case MenuElement.CLUT_DATA:
                    width = int_from_bytes(f.read(2))
                    clut_data.append(f.read(2 * width))
                case MenuElement.LAYOUT:
                    count = int_from_bytes(f.read(2))
                    for _ in range(count):
                        layouts.append(Layout(*struct.unpack('<2H', f.read(4))))

        return cls(images, clut_settings, components, tiles, clut_data, layouts, unused=unused)

    def write(self, f: BinaryIO, **kwargs):
        f.write(self.unused.to_bytes(4, 'little'))

        if num_images := len(self.images):
            f.write(MenuElement.IMAGE.to_bytes(2, 'little'))
            f.write(num_images.to_bytes(2, 'little'))
            for image in self.images:
                f.write(image.width.to_bytes(2, 'little'))
                f.write(image.height.to_bytes(2, 'little'))
                f.write(image.data)

        if num_cluts := len(self.clut_data):
            f.write(MenuElement.CLUT_DATA.to_bytes(2, 'little'))
            f.write(num_cluts.to_bytes(2, 'little'))
            for clut_data in self.clut_data:
                f.write((len(clut_data) // 2).to_bytes(2, 'little'))
                f.write(clut_data)

        if num_cluts := len(self.clut_settings):
            f.write(MenuElement.CLUT_INFO.to_bytes(2, 'little'))
            f.write(num_cluts.to_bytes(2, 'little'))
            for clut_info in self.clut_settings:
                f.write(bytes(astuple(clut_info)))

        if num_layouts := len(self.layouts):
            f.write(MenuElement.LAYOUT.to_bytes(2, 'little'))
            f.write(num_layouts.to_bytes(2, 'little'))
            for layout in self.layouts:
                f.write(struct.pack('<2H', *astuple(layout)))

        if num_tiles := len(self.tiles):
            f.write(MenuElement.TILE.to_bytes(2, 'little'))
            f.write(num_tiles.to_bytes(2, 'little'))
            for tile in self.tiles:
                f.write(struct.pack('<6H6BH', (tile.width, tile.height, tile.layouts[0], tile.layouts[1],
                                               tile.layouts[2], tile.layouts[3], tile.x_scale_index, tile.image_index,
                                               tile.x_offset, tile.y_offset, tile.clut_index, tile.unused,
                                               tile.unknown)))

        if num_components := len(self.components):
            f.write(MenuElement.COMPONENT.to_bytes(2, 'little'))
            f.write(num_components.to_bytes(2, 'little'))
            for component in self.components:
                f.write(struct.pack('<11H', *astuple(component)))

        f.write(MenuElement.PRE_END.to_bytes(2, 'little'))
        f.write(MenuElement.END.to_bytes(2, 'little'))

    @classmethod
    def import_(cls, path: Path, fmt: str = None) -> Self:
        raise NotImplementedError('Menus do not currently support editing')

    def export(self, path: Path, fmt: str = None) -> Path:
        if fmt == 'render':
            self.render().save(path)
            return path

        path.mkdir(exist_ok=True)
        for i, image in enumerate(self):
            new_path = path / f'{i:03}.{fmt}'
            image.save(new_path)

        return path
