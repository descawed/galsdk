from abc import ABC, abstractmethod

from panda3d.core import NodePath, PandaNode, Texture

from galsdk.coords import Point


class RoomObject(ABC):
    node_path: NodePath | None

    def __init__(self, name: str, position: Point, angle: float):
        self.name = name
        self.position = position
        self.angle = angle
        self.node_path = NodePath(PandaNode(f'{name}_object'))
        self.node_path.setTag('object_name', name)
        self.original_model = None
        self.model_node = None
        self.scene = None
        self.color = (0., 0., 0., 0.)

    def add_to_scene(self, scene: NodePath):
        self.scene = scene
        self.node_path.reparentTo(scene)
        self.update()

    def remove_from_scene(self):
        if self.node_path:
            self.node_path.removeNode()
            self.node_path = None
            self.scene = None

    def update_model(self):
        if model := self.get_model():
            if self.original_model is not model:
                self.original_model = model
                if self.model_node:
                    self.model_node.removeNode()
                # because we frequently reuse the same model (i.e. same NodePath) for different instances of the same
                # character, we need to make separate instances of the model for each RoomObject, otherwise we'll have
                # problems when a room includes more than one of the same type of NPC
                self.model_node = self.original_model.instanceUnderNode(self.node_path, f'{self.name}_instance')

    def update_texture(self):
        if self.model_node:
            if texture := self.get_texture():
                self.model_node.setTexture(texture, 1)
            else:
                self.model_node.setColor(*self.color)

    def update_position(self):
        self.node_path.setPos(self.position.panda_x, self.position.panda_y, self.position.panda_z)
        self.node_path.setH(self.angle)

    def set_color(self, color: tuple[float, float, float, float]):
        self.color = color
        self.update_texture()

    def update(self):
        self.update_model()
        self.update_texture()
        self.update_position()

    def show(self):
        self.node_path.show()

    def hide(self):
        self.node_path.hide()

    @abstractmethod
    def get_model(self) -> NodePath | None:
        pass

    def get_texture(self) -> Texture | None:
        return None
