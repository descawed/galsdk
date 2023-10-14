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
        return Interactable(self.id, self.position.game_x, self.position.game_z, self.width.game_units,
                            self.height.game_units), self.trigger
