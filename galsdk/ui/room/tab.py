import math
import tkinter as tk
from tkinter import ttk

from direct.showbase.ShowBase import ShowBase

from galsdk.module import RoomModule, ColliderType
from galsdk.project import Project, Stage
from galsdk.room import CircleColliderObject, RectangleColliderObject, TriangleColliderObject, WallColliderObject
from galsdk.ui.room.collider import ColliderEditor, ColliderObject
from galsdk.ui.room.replaceable import Replaceable
from galsdk.ui.tab import Tab
from galsdk.ui.viewport import Viewport


class RoomViewport(Viewport):
    def __init__(self, base: ShowBase, width: int, height: int, *args, **kwargs):
        super().__init__('room', base, width, height, *args, **kwargs)
        self.wall = None
        self.colliders = []

    def clear(self):
        self.wall = None
        for collider in self.colliders:
            collider.remove_from_scene()
        self.colliders = []

    def replace_collider(self, index: int, collider: ColliderObject):
        self.colliders[index].remove_from_scene()
        self.colliders[index] = collider
        collider.add_to_scene(self.render_target)

    def set_room(self, module: RoomModule):
        self.clear()

        rect_iter = iter(module.layout.rectangle_colliders)
        tri_iter = iter(module.layout.triangle_colliders)
        circle_iter = iter(module.layout.circle_colliders)
        camera_distance = 0.
        module_name = module.name or 'UNKWN'

        for collider in module.layout.colliders:
            index = len(self.colliders)
            is_wall = False
            object_name = f'room{module_name}_collider{index}'
            match collider.type:
                case ColliderType.WALL:
                    collider_object = self.wall = WallColliderObject(object_name, next(rect_iter))
                    is_wall = True
                    # calculate how far away the camera needs to be to fit the entire area on the screen
                    height = max(abs(self.wall.width.panda_units), abs(self.wall.height.panda_units))
                    fov = math.radians(self.camera.node().getLens().getVfov())
                    camera_distance = height / 2 / math.tan(fov / 2)
                case ColliderType.RECTANGLE:
                    collider_object = RectangleColliderObject(object_name, next(rect_iter))
                case ColliderType.TRIANGLE:
                    collider_object = TriangleColliderObject(object_name, next(tri_iter))
                case ColliderType.CIRCLE:
                    collider_object = CircleColliderObject(object_name, next(circle_iter))
                case _:
                    continue

            if not is_wall:
                collider_object.position.game_y += 1
            collider_object.add_to_scene(self.render_target)
            self.colliders.append(collider_object)

        self.camera.setPos(self.wall.position.panda_x, self.wall.position.panda_y,
                           self.wall.position.panda_z + camera_distance)
        self.camera.lookAt(self.wall.node_path)


class RoomTab(Tab):
    """Tab for inspecting and editing rooms in the game"""

    def __init__(self, project: Project, base: ShowBase):
        super().__init__('Room', project)
        self.base = base
        self.current_room = None
        self.detail_widget = None
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

        self.tree.bind('<<TreeviewSelect>>', self.select_item)

    def set_detail_widget(self, widget: ttk.Frame | None):
        if self.detail_widget:
            self.detail_widget.grid_forget()
            self.detail_widget.destroy()
        self.detail_widget = widget
        if self.detail_widget:
            self.detail_widget.grid(row=0, column=2)

    def select_item(self, _):
        iid = self.tree.selection()[0]
        room_level_ids = ['room', 'actors', 'colliders', 'cameras', 'cuts', 'triggers']
        if any(iid.startswith(f'{room_level_id}_') for room_level_id in room_level_ids):
            room_id = int(iid.split('_')[1])
            if self.current_room != room_id:
                self.current_room = room_id
                self.viewport.set_room(self.rooms[room_id])
                colliders_iid = f'colliders_{room_id}'
                if not self.tree.get_children(colliders_iid):
                    for i in range(len(self.viewport.colliders)):
                        self.tree.insert(colliders_iid, tk.END, text=f'#{i}', iid=f'collider_{i}_{room_id}')
            self.set_detail_widget(None)
        elif iid.startswith('collider_'):
            pieces = iid.split('_')
            collider_id = int(pieces[1])
            room_id = int(pieces[2])
            if self.current_room != room_id:
                self.current_room = room_id
                self.viewport.set_room(self.rooms[room_id])
            collider = Replaceable(self.viewport.colliders[collider_id],
                                   lambda c: self.viewport.replace_collider(collider_id, c))
            editor = ColliderEditor(collider, self)
            self.set_detail_widget(editor)

    def set_active(self, is_active: bool):
        self.viewport.set_active(is_active)
