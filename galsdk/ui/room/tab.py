import math
import tkinter as tk
from tkinter import ttk

from direct.showbase.ShowBase import ShowBase
from panda3d.core import GeomNode, TransparencyAttrib

from galsdk.module import RoomModule, ColliderType
from galsdk.project import Project, Stage
from galsdk.room import RectangleColliderObject, TriangleColliderObject, WallColliderObject
from galsdk.ui.tab import Tab
from galsdk.ui.viewport import Viewport


class RoomViewport(Viewport):
    def __init__(self, base: ShowBase, width: int, height: int, *args, **kwargs):
        super().__init__('room', base, width, height, *args, **kwargs)
        self.wall = None
        self.wall_node_path = None
        self.colliders = []

    def set_room(self, module: RoomModule):
        self.wall = None
        self.wall_node_path = None
        self.colliders = []

        rect_iter = iter(module.layout.rectangle_colliders)
        tri_iter = iter(module.layout.triangle_colliders)
        circle_iter = iter(module.layout.circle_colliders)
        camera_distance = 0.
        name = module.name or 'UNKWN'

        for collider in module.layout.colliders:
            index = len(self.colliders)
            is_wall = False
            match collider.type:
                case ColliderType.WALL:
                    collider_object = self.wall = WallColliderObject(next(rect_iter))
                    self.colliders.append(self.wall)
                    is_wall = True
                    # calculate how far away the camera needs to be to fit the entire area on the screen
                    height = max(self.wall.size)
                    fov = math.radians(self.camera.node().getLens().getVfov())
                    camera_distance = height / 2 / math.tan(fov / 2)
                case ColliderType.RECTANGLE:
                    self.colliders.append(collider_object := RectangleColliderObject(next(rect_iter)))
                case ColliderType.TRIANGLE:
                    self.colliders.append(collider_object := TriangleColliderObject(next(tri_iter)))
                case _:
                    continue

            model = collider_object.get_model()
            node = GeomNode(f'room{name}_collider{index}')
            node.addGeom(model)
            node_path = self.render_target.attachNewNode(node)
            offset = 0 if is_wall else 0.1
            node_path.setPos(collider_object.x, collider_object.y, collider_object.z + offset)
            node_path.reparentTo(self.render_target)
            node_path.setTag('collider', str(index))
            node_path.setTransparency(TransparencyAttrib.M_alpha)
            node_path.setColor(*(c / 255 for c in collider_object.color))
            if is_wall:
                self.wall_node_path = node_path

        self.camera.setPos(self.wall.x, self.wall.y, self.wall.z + camera_distance)
        self.camera.lookAt(self.wall_node_path)


class RoomTab(Tab):
    """Tab for inspecting and editing rooms in the game"""

    def __init__(self, project: Project, base: ShowBase):
        super().__init__('Room', project)
        self.base = base
        self.rooms = []

        self.tree = ttk.Treeview(self, selectmode='browse', show='tree')
        scroll = ttk.Scrollbar(self, command=self.tree.yview, orient='vertical')
        self.tree.configure(yscrollcommand=scroll.set)

        for stage in Stage:
            stage: Stage
            self.tree.insert('', tk.END, text=f'Stage {stage}', iid=stage, open=False)

            for room in self.project.get_stage_rooms(stage):
                room_id = len(self.rooms)
                self.rooms.append(room)
                iid = f'room_{room_id}'
                self.tree.insert(stage, tk.END, text=room.name, iid=iid)

                actor_iid = f'actors_{room_id}'
                self.tree.insert(iid, tk.END, text='Actors', iid=actor_iid)
                collider_iid = f'colliders_{room_id}'
                self.tree.insert(iid, tk.END, text='Colliders', iid=collider_iid)
                camera_iid = f'cameras_{room_id}'
                self.tree.insert(iid, tk.END, text='Cameras', iid=camera_iid)
                cut_iid = f'cuts_{room_id}'
                self.tree.insert(iid, tk.END, text='Cuts', iid=cut_iid)
                trigger_iid = f'triggers_{room_id}'
                self.tree.insert(iid, tk.END, text='Triggers', iid=trigger_iid)

        self.viewport = RoomViewport(self.base, 1024, 768, self)

        self.tree.grid(row=0, column=0, sticky=tk.NS + tk.W)
        scroll.grid(row=0, column=1, sticky=tk.NS)
        self.viewport.grid(row=0, column=3, sticky=tk.NS + tk.E)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(3, weight=1)

        self.tree.bind('<<TreeviewSelect>>', self.select_movie)

    def select_movie(self, _):
        iid = self.tree.selection()[0]
        if iid.startswith('room_'):
            index = int(iid.split('_')[1])
            self.viewport.set_room(self.rooms[index])
