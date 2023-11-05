from panda3d.core import NodePath, Texture

from galsdk.coords import Point
from galsdk.model import ActorModel
from galsdk.module import ActorInstance
from galsdk.room.object import RoomObject


class ActorObject(RoomObject):
    def __init__(self, name: str, model: ActorModel | None, instance: ActorInstance):
        super().__init__(name, Point(instance.x, instance.y, instance.z), 360 * instance.orientation / 4096)
        self.model = model
        self.id = instance.id
        self.type = instance.type
        self.unknown1 = instance.unknown1
        self.unknown2 = instance.unknown2

    @property
    def actor_name(self) -> str:
        return self.model.name if self.model else 'None'

    @property
    def can_rotate(self) -> bool:
        return True

    def get_model(self) -> NodePath | None:
        return self.model.get_panda3d_model() if self.model else None

    def get_texture(self) -> Texture | None:
        return self.model.get_panda3d_texture() if self.model else None

    def as_actor_instance(self) -> ActorInstance:
        return ActorInstance(self.id, self.type, self.position.game_x, self.position.game_y, self.position.game_z,
                             self.unknown1, int(self.angle * 4096 / 360), self.unknown2)
