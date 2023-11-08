from direct.showbase.Loader import Loader
from panda3d.core import NodePath

from galsdk.coords import Point
from galsdk.module import Entrance
from galsdk.room.object import RoomObject


class EntranceObject(RoomObject):
    def __init__(self, name: str, entrance: Entrance, loader: Loader):
        super().__init__(name, Point(entrance.x, entrance.y, entrance.z), 360 * entrance.angle / 4096)
        self.room_index = entrance.room_index
        self.model = loader.loadModel('arrow.egg')
        self.model.setP(-90)
        self.model.setZ(10)
        self.model.setScale(2)
        self.model.reparentTo(self.node_path)
        self.color = (0.5, 0.5, 0.5, 0.9)

    @property
    def can_rotate(self) -> bool:
        return True

    def get_model(self) -> NodePath | None:
        return None

    def as_entrance(self) -> Entrance:
        return Entrance(self.room_index, self.position.game_x, self.position.game_y, self.position.game_z,
                        int(self.angle * 4096 / 360))
