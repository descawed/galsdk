import dataclasses

from galsdk.module import Interactable, RectangleCollider, Trigger
from galsdk.room.collider import RectangleColliderObject


TRIGGER_COLOR = (0., 0., 1., 0.5)


class TriggerObject(RectangleColliderObject):
    def __init__(self, name: str, interactable: Interactable, trigger: Trigger | None):
        bounds = RectangleCollider(interactable.x_pos, interactable.z_pos, interactable.x_size, interactable.z_size)
        super().__init__(name, bounds)
        self.color = TRIGGER_COLOR
        # we make a copy here so our changes don't affect the module before the user saves
        self.trigger = dataclasses.replace(trigger) if trigger else None
        self.id = interactable.id

    def as_interactable(self) -> tuple[Interactable, Trigger | None]:
        width = self.width.game_units
        height = self.height.game_units
        x = self.position.game_x - width // 2
        z = self.position.game_z - height // 2
        return Interactable(self.id, x, z, width, height), self.trigger

    @property
    def is_2d(self) -> bool:
        return True

    @property
    def can_resize(self) -> bool:
        return True
