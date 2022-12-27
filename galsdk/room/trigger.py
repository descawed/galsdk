from galsdk.module import Interactable, RectangleCollider, Trigger
from galsdk.room.collider import RectangleColliderObject


TRIGGER_COLOR = (0., 0., 1., 0.5)


class TriggerObject(RectangleColliderObject):
    def __init__(self, name: str, interactable: Interactable, trigger: Trigger):
        bounds = RectangleCollider(interactable.x_pos, interactable.z_pos, interactable.x_size, interactable.z_size)
        super().__init__(name, bounds)
        self.color = TRIGGER_COLOR
        self.trigger = trigger
        self.id = interactable.id
