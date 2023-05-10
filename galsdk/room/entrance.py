from direct.showbase.Loader import Loader
from panda3d.core import NodePath

from galsdk.coords import Point
from galsdk.module import Entrance
from galsdk.room.object import RoomObject


class EntranceObject(RoomObject):
    def __init__(self, name: str, entrance: Entrance, loader: Loader):
        super().__init__(name, Point(entrance.x, entrance.y, entrance.z), 360 * entrance.angle / 4096)
        self.room_index = entrance.room_index
        self.node_path = loader.loadModel('arrow.egg')
        self.color = (0.5, 0.5, 0.5, 0.9)

    def get_model(self) -> NodePath | None:
        return None
