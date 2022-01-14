import io
from typing import Iterable

from psx.tim import Tim


class TimDb:
    """
    A database of TIM images

    The game keeps TIM images for scene backgrounds and their associated masks in a combined database. This class reads
    and writes such databases.
    """

    images: list[Tim]

    def __init__(self):
        """Create a new, empty TIM database"""
        self.images = []

    def read(self, path: str):
        """
        Read a TIM database file

        :param path: Path to the database file
        """
        self.images = []
        with open(path, 'rb') as f:
            num_images = int.from_bytes(f.read(4), 'little')
            directory = [(int.from_bytes(f.read(4), 'little'), int.from_bytes(f.read(4), 'little'))
                         for _ in range(num_images)]
            for offset, size in directory:
                f.seek(offset)
                with io.BytesIO(f.read(size)) as buf:
                    self.images.append(Tim.read(buf))

    def write(self, path: str):
        """
        Write the images in this object out to a database file

        :param path: Path to the TIM database to be written
        """
        raw_tims = []
        for image in self.images:
            with io.BytesIO() as buf:
                image.write(buf)
                raw_tims.append(buf.getvalue())

        with open(path, 'wb') as f:
            f.write(len(self.images).to_bytes(4, 'little'))
            header_size = 4 + len(raw_tims)*8  # 2 32-bit integers per TIM
            offset = header_size
            for data in raw_tims:
                size = len(data)
                f.write(offset.to_bytes(4, 'little'))
                f.write(size.to_bytes(4, 'little'))
                offset += size
            for data in raw_tims:
                f.write(data)

    def __getitem__(self, item: int) -> Tim:
        """Get an image from the database"""
        return self.images[item]

    def __setitem__(self, key: int, value: Tim):
        """Set an image in the database"""
        self.images[key] = value

    def __iter__(self) -> Iterable[Tim]:
        """Iterate over images in the database"""
        yield from self.images

    def __len__(self) -> int:
        """Number of images in the database"""
        return len(self.images)

    def append(self, image: Tim):
        """
        Add a new image to the database

        :param image: The TIM image to add to the database
        """
        self.images.append(image)
