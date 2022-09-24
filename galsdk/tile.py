from PIL import Image

from psx.tim import Tim


class TileSet:
    def __init__(self, image: Tim, width: int, height: int):
        self.image = image
        self.width = width
        self.height = height
        self.per_row = image.width // width
        self.cluts = [self.image.to_image(i) for i in range(self.image.num_palettes)]

    def get(self, index: int, clut: int = 0) -> Image:
        image = self.cluts[clut]
        x = index % self.per_row * self.width
        y = index // self.per_row * self.height
        tile = image.crop((x, y, x + self.width, y + self.height))
        return tile

    def __getitem__(self, item: int) -> Image:
        return self.get(item)

    def __len__(self) -> int:
        num_rows = self.image.height // self.height
        return num_rows * self.per_row
