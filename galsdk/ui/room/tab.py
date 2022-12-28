import math
import tkinter as tk
from tkinter import ttk

from direct.showbase.ShowBase import ShowBase

from galsdk.manifest import Manifest
from galsdk.module import RoomModule, ColliderType
from galsdk.project import Project, Stage
from galsdk.room import CircleColliderObject, RectangleColliderObject, RoomObject, TriangleColliderObject,\
    WallColliderObject, TriggerObject, CameraCutObject, CameraObject, BillboardObject
from galsdk.tim import TimDb
from galsdk.ui.room.camera import CameraEditor
from galsdk.ui.room.collider import ColliderEditor, ColliderObject
from galsdk.ui.room.cut import CameraCutEditor
from galsdk.ui.room.replaceable import Replaceable
from galsdk.ui.room.trigger import TriggerEditor
from galsdk.ui.tab import Tab
from galsdk.ui.viewport import Viewport


class RoomViewport(Viewport):
    def __init__(self, base: ShowBase, width: int, height: int, stage_backgrounds: dict[Stage, Manifest],
                 *args, **kwargs):
        super().__init__('room', base, width, height, *args, **kwargs)
        self.wall = None
        self.selected_item = None
        self.colliders = []
        self.collider_node = self.render_target.attachNewNode('room_viewport_colliders')
        self.triggers = []
        self.trigger_node = self.render_target.attachNewNode('room_viewport_triggers')
        self.cuts = []
        self.cut_node = self.render_target.attachNewNode('room_viewport_cuts')
        self.cameras = []
        self.camera_node = self.render_target.attachNewNode('room_viewport_cameras')
        self.default_fov = self.camera.node().getLens().getMinFov()
        self.stage_backgrounds = stage_backgrounds
        self.current_stage = Stage.A
        self.background = None
        self.loaded_tims = {}

    def clear(self):
        self.wall = None
        self.selected_item = None
        if self.background:
            self.background.remove_from_scene()
            self.background = None
        self.loaded_tims = {}
        for obj in [*self.colliders, *self.triggers, *self.cuts, *self.cameras]:
            obj.remove_from_scene()
        self.colliders = []
        self.triggers = []
        self.cuts = []
        self.cameras = []

    def set_group_visibility(self, group: str, visibility: bool):
        if node_path := self.render_target.find(f'**/room_viewport_{group}'):
            if visibility:
                node_path.show()
            else:
                node_path.hide()

    def replace_item(self, item_type: str, index: int, item: RoomObject):
        container = getattr(self, item_type)
        old_object = container[index]
        is_selected = self.selected_item and self.selected_item[0] is old_object
        old_object.remove_from_scene()
        container[index] = item
        item.add_to_scene(self.render_target)
        if is_selected:
            self.select(item)

    def replace_collider(self, index: int, collider: ColliderObject):
        self.replace_item('colliders', index, collider)

    def replace_trigger(self, index: int, trigger: TriggerObject):
        self.replace_item('triggers', index, trigger)

    def calculate_screen_fill_distance(self, width: float, height: float) -> float:
        width = abs(width)
        height = abs(height)
        if width > height:
            dimension = width
            fov = self.camera.node().getLens().getHfov()
        else:
            dimension = height
            fov = self.camera.node().getLens().getVfov()
        fov = math.radians(fov)
        # according to the formula I found online, I'm supposed to be dividing dimension by 2, but I had to remove that
        # to get backgrounds to show up correctly. this does make the initial view of the floor layout more zoomed out
        # than I intended, but that's a minor issue.
        return dimension / math.tan(fov / 2)

    def get_default_camera_distance(self) -> float:
        return self.calculate_screen_fill_distance(self.wall.width.panda_units, self.wall.height.panda_units)

    def set_camera_view(self, camera: CameraObject | None):
        if self.background:
            self.background.remove_from_scene()
        if camera:
            # TODO: this should track changes to the camera in real-time. also, we should make the camera target
            #  targetable with set_target
            # FIXME: hide the camera model for the camera we're currently viewing
            self.clear_target()
            self.camera.setPos(camera.position.panda_x, camera.position.panda_y, camera.position.panda_z)
            self.camera.lookAt(camera.target.panda_x, camera.target.panda_y, camera.target.panda_z)
            self.camera.node().getLens().setMinFov(camera.fov)
            bg_tim = self.loaded_tims[camera.background.index][0]
            self.background = BillboardObject('room_viewport_background', bg_tim)
            self.background.add_to_scene(self.render_target)
            distance = self.calculate_screen_fill_distance(self.background.width, self.background.height)
            self.background.node_path.setPos(self.camera, 0, distance, 0)
            self.background.node_path.setHpr(self.camera, 0, 90, 0)
        else:
            self.camera.node().getLens().setMinFov(self.default_fov)
            camera_distance = self.get_default_camera_distance()
            self.max_zoom = camera_distance * 4
            self.set_target(self.wall.node_path, (0, 0, camera_distance))
            self.background = None

    def select(self, item: RoomObject | None):
        if self.selected_item:
            old_item = self.selected_item[0]
            r, g, b, _ = old_item.color
            a = self.selected_item[1]
            old_item.set_color((r, g, b, a))
            old_item.node_path.setDepthTest(True)
        if item:
            r, g, b, a = item.color
            self.selected_item = (item, a)
            item.set_color((r, g, b, 1.))
            item.node_path.setDepthTest(False)
        else:
            self.selected_item = None

    def set_room(self, module: RoomModule):
        self.clear()

        rect_iter = iter(module.layout.rectangle_colliders)
        tri_iter = iter(module.layout.triangle_colliders)
        circle_iter = iter(module.layout.circle_colliders)
        module_name = module.name or 'UNKWN'
        self.current_stage = Stage(module_name[0])

        for cut in module.layout.cuts:
            object_name = f'room{module_name}_cut{len(self.cuts)}'
            cut_object = CameraCutObject(object_name, cut)
            cut_object.position.game_y += 1
            cut_object.add_to_scene(self.cut_node)
            self.cuts.append(cut_object)

        for collider in module.layout.colliders:
            index = len(self.colliders)
            is_wall = False
            object_name = f'room{module_name}_collider{index}'
            match collider.type:
                case ColliderType.WALL:
                    collider_object = self.wall = WallColliderObject(object_name, next(rect_iter))
                    is_wall = True
                case ColliderType.RECTANGLE:
                    collider_object = RectangleColliderObject(object_name, next(rect_iter))
                case ColliderType.TRIANGLE:
                    collider_object = TriangleColliderObject(object_name, next(tri_iter))
                case ColliderType.CIRCLE:
                    collider_object = CircleColliderObject(object_name, next(circle_iter))
                case _:
                    continue

            if not is_wall:
                collider_object.position.game_y += 2
            collider_object.add_to_scene(self.collider_node)
            self.colliders.append(collider_object)

        for interactable, trigger in zip(module.layout.interactables, module.triggers.triggers, strict=True):
            object_name = f'room{module_name}_trigger{len(self.triggers)}'
            trigger_object = TriggerObject(object_name, interactable, trigger)
            trigger_object.position.game_y += 3
            trigger_object.add_to_scene(self.trigger_node)
            self.triggers.append(trigger_object)

        for camera, background in zip(module.layout.cameras, module.backgrounds.backgrounds, strict=True):
            object_name = f'room{module_name}_camera{len(self.cameras)}'
            camera_object = CameraObject(object_name, camera, background, self.base.loader)
            camera_object.add_to_scene(self.camera_node)
            self.cameras.append(camera_object)
            if camera_object.background.index not in self.loaded_tims:
                db = TimDb()
                with open(self.stage_backgrounds[self.current_stage][camera_object.background.index].path, 'rb') as f:
                    db.read(f)
                self.loaded_tims[camera_object.background.index] = db

        self.set_camera_view(None)


class RoomTab(Tab):
    """Tab for inspecting and editing rooms in the game"""

    def __init__(self, project: Project, base: ShowBase):
        super().__init__('Room', project)
        self.base = base
        self.current_room = None
        self.detail_widget = None
        self.menu_item = None
        self.rooms = []
        self.visibility = {'colliders': True, 'cuts': True, 'triggers': True, 'cameras': True}

        key_items = list(self.project.get_items(True))
        self.item_names = [f'Unused #{i}' for i in range(len(key_items))]
        for item in key_items:
            self.item_names[item.id] = item.name

        stage_backgrounds = {}

        self.group_menu = tk.Menu(self, tearoff=False)
        self.group_menu.add_command(label='Hide', command=self.toggle_current_group)

        self.tree = ttk.Treeview(self, selectmode='browse', show='tree')
        scroll = ttk.Scrollbar(self, command=self.tree.yview, orient='vertical')
        self.tree.configure(yscrollcommand=scroll.set)

        for stage in Stage:
            stage: Stage
            self.tree.insert('', tk.END, text=f'Stage {stage}', iid=stage, open=False)

            stage_backgrounds[stage] = self.project.get_stage_backgrounds(stage)

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

        self.viewport = RoomViewport(self.base, 1024, 768, stage_backgrounds, self)

        self.tree.grid(row=0, column=0, sticky=tk.NS + tk.W)
        scroll.grid(row=0, column=1, sticky=tk.NS)
        self.viewport.grid(row=0, column=3, sticky=tk.NS + tk.E)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(3, weight=1)

        self.tree.bind('<<TreeviewSelect>>', self.select_item)
        self.tree.bind('<Button-3>', self.handle_right_click)

    def set_room(self, room_id: int):
        if self.current_room != room_id:
            self.current_room = room_id
            self.viewport.set_room(self.rooms[room_id])

    def toggle_current_group(self, *_):
        if self.menu_item:
            for group in self.visibility:
                if self.menu_item.startswith(f'{group}_'):
                    is_visible = not self.visibility[group]
                    self.viewport.set_group_visibility(group, is_visible)
                    self.visibility[group] = is_visible
                    break

    def handle_right_click(self, event: tk.Event):
        iid = self.tree.identify_row(event.y)
        for group in self.visibility:
            if iid.startswith(f'{group}_'):
                room_id = int(iid.split('_')[1])
                if self.current_room != room_id:
                    self.tree.selection_set(iid)
                self.group_menu.entryconfigure(1, label='Hide' if self.visibility[group] else 'Show')
                self.group_menu.post(event.x_root, event.y_root)
                self.menu_item = iid

    def set_detail_widget(self, widget: ttk.Frame | None):
        if self.detail_widget:
            self.detail_widget.grid_forget()
            self.detail_widget.destroy()
        self.detail_widget = widget
        if self.detail_widget:
            self.detail_widget.grid(row=0, column=2)

    def add_children(self, room_id: int, group: str, container: list):
        iid = f'{group}s_{room_id}'
        if not self.tree.get_children(iid):
            for i in range(len(container)):
                self.tree.insert(iid, tk.END, text=f'#{i}', iid=f'{group}_{i}_{room_id}')

    def select_item(self, _):
        iid = self.tree.selection()[0]
        room_level_ids = ['room', 'actors', 'colliders', 'cameras', 'cuts', 'triggers']
        object_ids = ['collider', 'trigger', 'cut', 'camera']
        if any(iid.startswith(f'{room_level_id}_') for room_level_id in room_level_ids):
            room_id = int(iid.split('_')[1])
            if self.current_room != room_id:
                self.set_room(room_id)
                self.add_children(room_id, 'collider', self.viewport.colliders)
                self.add_children(room_id, 'cut', self.viewport.cuts)
                self.add_children(room_id, 'trigger', self.viewport.triggers)
                self.add_children(room_id, 'camera', self.viewport.cameras)
            self.set_detail_widget(None)
            self.viewport.select(None)
        elif any(iid.startswith(f'{object_id}_') for object_id in object_ids):
            pieces = iid.split('_')
            object_type = pieces[0]
            object_id = int(pieces[1])
            room_id = int(pieces[2])
            self.set_room(room_id)
            camera_view = None
            match object_type:
                case 'collider':
                    collider = Replaceable(self.viewport.colliders[object_id],
                                           lambda c: self.viewport.replace_collider(object_id, c))
                    editor = ColliderEditor(collider, self)
                    obj = collider.object
                case 'trigger':
                    obj = self.viewport.triggers[object_id]
                    editor = TriggerEditor(obj, self.item_names, self)
                case 'cut':
                    obj = self.viewport.cuts[object_id]
                    editor = CameraCutEditor(obj, self)
                case 'camera':
                    camera_view = obj = self.viewport.cameras[object_id]
                    editor = CameraEditor(obj, self)
                case _:
                    self.set_detail_widget(None)
                    self.viewport.select(None)
                    return
            self.set_detail_widget(editor)
            self.viewport.select(obj)
            self.viewport.set_camera_view(camera_view)

    def set_active(self, is_active: bool):
        self.viewport.set_active(is_active)