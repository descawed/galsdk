import dataclasses

from galsdk.module import Interactable, RectangleCollider, Trigger
from galsdk.room.collider import RectangleColliderObject


TRIGGER_COLOR = (0., 0., 1., 0.5)


class TriggerObject(RectangleColliderObject):
    def __init__(self, name: str, interactable: Interactable | None, trigger: Trigger | None):
        assert interactable is not None or trigger is not None, 'Tried to create a TriggerObject with no data'

        if interactable is None:
            bounds = RectangleCollider(0, 0, 0, 0)
        else:
            bounds = RectangleCollider(interactable.x_pos, interactable.z_pos, interactable.x_size, interactable.z_size)
        super().__init__(name, bounds)
        self.color = TRIGGER_COLOR
        # we make a copy here so our changes don't affect the module before the user saves
        self.trigger = dataclasses.replace(trigger) if trigger else None
        self.id = interactable.id if interactable else None

    def as_interactable(self) -> tuple[Interactable | None, Trigger | None]:
        if self.has_interactable:
            width = self.width.game_units
            height = self.height.game_units
            x = self.position.game_x - width // 2
            z = self.position.game_z - height // 2
            interactable = Interactable(self.id, x, z, width, height)
        else:
            interactable = None
        return interactable, self.trigger

    @property
    def has_trigger(self) -> bool:
        return self.trigger is not None

    @property
    def has_interactable(self) -> bool:
        return self.id is not None
