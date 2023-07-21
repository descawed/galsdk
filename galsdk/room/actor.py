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

    @property
    def actor_name(self) -> str:
        return self.model.name if self.model else 'None'

    def get_model(self) -> NodePath | None:
        return self.model.get_panda3d_model() if self.model else None

    def get_texture(self) -> Texture | None:
        return self.model.get_panda3d_texture() if self.model else None
