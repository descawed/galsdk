import math
import tkinter as tk
from itertools import zip_longest
from pathlib import Path
from tkinter import ttk
from typing import Callable, Literal

from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import (CollisionHandlerQueue, CollisionNode, CollisionPlane, CollisionRay, CollisionTraverser,
                          GeomNode, KeyboardButton, MouseButton, NodePath, Plane, Vec3)
from PIL import Image

from galsdk import util
from galsdk.animation import AnimationDb
from galsdk.model import ActorModel
from galsdk.module import (ActorInstance, CircleCollider, Collider, ColliderType, RectangleCollider, RoomModule,
                           TriangleCollider)
from galsdk.project import Project
from galsdk.game import Stage
from galsdk.room import (CircleColliderObject, RectangleColliderObject, RoomObject, TriangleColliderObject,
                         WallColliderObject, TriggerObject, CameraCutObject, CameraObject, BillboardObject, ActorObject,
                         EntranceObject)
from galsdk.tim import TimDb
from galsdk.ui.animation import ActiveAnimation
from galsdk.ui.room.actor import ActorEditor
from galsdk.ui.room.camera import CameraEditor
from galsdk.ui.room.collider import ColliderEditor, ColliderObject
from galsdk.ui.room.cut import CameraCutEditor
from galsdk.ui.room.entrance import EntranceEditor
from galsdk.ui.room.replaceable import Replaceable
from galsdk.ui.room.trigger import TriggerEditor
from galsdk.ui.tab import Tab
from galsdk.ui.viewport import Cursor, Viewport
from psx.tim import Transparency


class RoomViewport(Viewport):
    CAMERA_TARGET_WIDTH = 1.78
    CAMERA_TARGET_HEIGHT = 2.
    MOVE_PER_SECOND = 15.

    def __init__(self, base: ShowBase, width: int, height: int, project: Project, *args, **kwargs):
        super().__init__('room', base, width, height, *args, **kwargs)
        self.name = None
        self.room_id = -1

        self.key_listener = None
        self.last_key_time = 0.
        self.select_listeners = []

        self.picker_node = CollisionNode('room_viewport_mouse_ray')
        self.picker_node.setFromCollideMask(GeomNode.getDefaultCollideMask())
        self.picker_ray = CollisionRay()
        self.picker_node.addSolid(self.picker_ray)

        self.collision_traverser = CollisionTraverser('room_viewport_traverser')
        self.collision_queue = CollisionHandlerQueue()

        # we use this plane when dragging to detect the point where the mouse has dragged to
        self.horizontal_plane = CollisionPlane(Plane(Vec3(0, 0, 1), Vec3(0, 0, 0)))
        self.horizontal_node_path = None

        self.wall = None
        self.selected_item = None
        self.camera_target = None
        self.camera_target_model = None

        self.colliders = []
        self.collider_node = self.render_target.attachNewNode('room_viewport_colliders')
        self.triggers = []
        self.trigger_node = self.render_target.attachNewNode('room_viewport_triggers')
        self.cuts = []
        self.cut_node = self.render_target.attachNewNode('room_viewport_cuts')
        self.cameras = []
        self.camera_node = self.render_target.attachNewNode('room_viewport_cameras')
        self.actors = []
        self.actor_node = self.render_target.attachNewNode('room_viewport_actors')
        self.entrance_sets = []
        self.entrances = []
        self.entrance_node = self.render_target.attachNewNode('room_viewport_entrances')

        self.default_fov = None
        self.project = project
        self.stage_backgrounds = {}
        for stage in Stage:
            stage: Stage
            self.stage_backgrounds[stage] = self.project.get_stage_backgrounds(stage)
        self.actor_models = list(self.project.get_actor_models(True))
        self.actor_animations = []
        self.anim_manifest = self.project.get_animations()
        self.anim_dbs = {}
        self.current_stage = Stage.A
        self.background = None
        self.current_bg = 0
        self.current_entrance_set = -1
        self.num_bgs = 0
        self.loaded_tims = {}
        self.actor_layouts = []
        self.current_layout = -1
        self.camera_view = None
        self.missing_bg = Image.open(Path.cwd() / 'assets' / 'missing_bg.png')
        self.target_icon = Image.open(Path.cwd() / 'assets' / 'target.png')

    def clear(self):
        self.name = None
        self.wall = None
        self.selected_item = None
        if self.background:
            self.background.remove_from_scene()
            self.background = None
        self.loaded_tims = {}
        for obj in [*self.colliders, *self.triggers, *self.cuts, *self.cameras, *self.actors, *self.entrances]:
            obj.remove_from_scene()
        self.colliders = []
        self.triggers = []
        self.cuts = []
        self.cameras = []
        self.entrance_sets = []
        self.entrances = []
        self.actor_layouts = []
        self.actors = []
        for animation in self.actor_animations:
            if animation:
                animation.remove()
        self.actor_animations = []
        self.current_entrance_set = -1
        self.current_layout = -1
        self.current_stage = Stage.A

    def on_select(self, listener: Callable[[str], None]):
        self.select_listeners.append(listener)

    def get_anim_db(self, index: int) -> AnimationDb:
        if index not in self.anim_dbs:
            anim_set = self.anim_manifest[index]
            with anim_set.path.open('rb') as f:
                self.anim_dbs[index] = AnimationDb.read(f)

        return self.anim_dbs[index]

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
        if self.wall:
            return self.calculate_screen_fill_distance(self.wall.width.panda_units, self.wall.height.panda_units)
        return 20.

    def update_camera_view(self):
        if self.camera_view:
            self.camera_target.setPos(self.camera_view.target.panda_x, self.camera_view.target.panda_y,
                                      self.camera_view.target.panda_z)
            self.camera_target.setHpr(0, 0, 0)
            self.set_target(self.camera_target)
            self.camera.setPos(self.render_target, self.camera_view.position.panda_x, self.camera_view.position.panda_y,
                               self.camera_view.position.panda_z)
            self.camera.lookAt(self.camera_target)
            self.camera_target_model.setHpr(self.camera, 0, 90, 0)
            self.camera.node().getLens().setMinFov(self.camera_view.fov)
            if self.background:
                distance = self.calculate_screen_fill_distance(self.background.width, self.background.height)
                self.background.node_path.setPos(0, distance, 0)
                self.background.node_path.setHpr(0, 90, 0)

    def update_actor(self, actor: ActorObject) -> tuple[int, int]:
        actor_id = self.actors.index(actor)
        if animation := self.actor_animations[actor_id]:
            animation.remove()
        self.actor_animations[actor_id] = self.start_actor_animation(actor.as_actor_instance())[1]
        return self.current_layout, actor_id

    def set_bg(self):
        if self.background:
            self.background.remove_from_scene()

        bg_index = self.camera_view.backgrounds[self.current_bg].index
        if bg_index == -1:
            bg_image = self.missing_bg
        else:
            bg_image = self.loaded_tims[bg_index][0].to_image(0, Transparency.NONE)
        self.background = BillboardObject('room_viewport_background', bg_image)
        self.background.add_to_scene(self.camera)
        self.update_camera_view()

    def select_bg(self, index: int):
        self.current_bg = index
        self.set_bg()

    def set_camera_view(self, camera: CameraObject | None):
        if self.default_fov is None and self.camera is not None:
            self.default_fov = self.camera.node().getLens().getMinFov()

        if self.background:
            self.background.remove_from_scene()
            self.background = None

        if not self.camera_target:
            self.camera_target = self.render_target.attachNewNode('room_viewport_camera_target')
            width = self.CAMERA_TARGET_WIDTH / 2
            height = self.CAMERA_TARGET_HEIGHT / 2
            geom = util.make_quad(
                (-width, -height),
                (width, -height),
                (width, height),
                (-width, height),
                True,
            )
            node = GeomNode('room_viewport_camera_target_model')
            node.addGeom(geom)
            self.camera_target_model = NodePath(node)
            self.camera_target_model.setTexture(util.create_texture_from_image(self.target_icon), 1)
            self.camera_target_model.reparentTo(self.camera_target)

        # unhide the old camera
        if self.camera_view:
            self.camera_view.show()

        self.camera_view = camera
        if camera:
            self.camera_target.show()
            # TODO: implement camera orientation and scale
            self.camera_view.hide()  # hide the model for the current camera angle so it's not in the way
            self.set_bg()
        else:
            self.camera_target.hide()
            self.camera.node().getLens().setMinFov(self.default_fov)
            camera_distance = self.get_default_camera_distance()
            self.max_zoom = camera_distance * 4
            if self.wall:
                self.set_target(self.wall.node_path, (0, 0, camera_distance))
            else:
                self.set_target(self.camera_target)

    def select(self, item: RoomObject | None):
        if self.selected_item:
            old_item = self.selected_item[0]
            r, g, b, _ = old_item.color
            a = self.selected_item[1]
            old_item.set_color((r, g, b, a))
            if old_item.node_path:
                old_item.node_path.setDepthTest(True)
        if item:
            r, g, b, a = item.color
            self.selected_item = (item, a)
            item.set_color((r, g, b, 1.))
            # FIXME: doesn't look good on actor models
            item.node_path.setDepthTest(False)
        else:
            self.selected_item = None

    def start_actor_animation(self, instance: ActorInstance) -> tuple[ActorModel | None, ActiveAnimation | None]:
        if instance.type >= 0:
            model = self.actor_models[instance.type]
            if model.anim_index is not None:
                anim_set = self.get_anim_db(model.anim_index)
                # FIXME: this is a hack because it relies on the fact that get_panda3d_model caches its result, so
                #  ActorObject will get the same NodePath
                animation = ActiveAnimation(self.base, f'room{self.name}_anim{instance.id}',
                                            model.get_panda3d_model(), anim_set[0])
                animation.play()
                return model, animation
            else:
                return model, None

        return None, None

    def set_actor_layout(self, index: int):
        if self.current_layout == index:
            return

        self.current_layout = index
        if self.actors:
            for actor in self.actors:
                actor.remove_from_scene()
            self.actors = []
            for animation in self.actor_animations:
                if animation:
                    animation.remove()
            self.actor_animations = []

        layout = self.actor_layouts[index]
        for actor_instance in layout.actors:
            model, animation = self.start_actor_animation(actor_instance)
            self.actor_animations.append(animation)
            actor = ActorObject(f'layout_{self.current_layout}_actor_{len(self.actors)}_{self.room_id}', model,
                                actor_instance)
            actor.add_to_scene(self.actor_node)
            self.actors.append(actor)

    def set_entrance_set(self, index: int):
        if self.current_entrance_set == index:
            return

        self.current_entrance_set = index
        for entrance_object in self.entrances:
            entrance_object.remove_from_scene()

        self.entrances = []
        for entrance in self.entrance_sets[index]:
            object_name = f'entrance-set_{self.current_entrance_set}_entrance_{len(self.entrances)}_{self.room_id}'
            entrance_object = EntranceObject(object_name, entrance, self.base.loader)
            entrance_object.add_to_scene(self.entrance_node)
            self.entrances.append(entrance_object)

    def set_room(self, module: RoomModule, room_id: int):
        self.clear()

        rect_iter = iter(module.layout.rectangle_colliders)
        tri_iter = iter(module.layout.triangle_colliders)
        circle_iter = iter(module.layout.circle_colliders)
        self.name = module.name or 'UNKWN'
        self.room_id = room_id
        self.current_stage = Stage(self.name[0])
        self.current_bg = 0

        for cut in module.layout.cuts:
            object_name = f'cut_{len(self.cuts)}_{room_id}'
            cut_object = CameraCutObject(object_name, cut)
            # FIXME: use proper depth sorting instead of this hack, which doesn't look right in many circumstances
            cut_object.position.game_y += 1
            cut_object.add_to_scene(self.cut_node)
            self.cuts.append(cut_object)

        for collider in module.layout.colliders:
            index = len(self.colliders)
            is_wall = False
            object_name = f'collider_{index}_{room_id}'
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

        # I used to have strict=True here, but there's one room (D1003) that has interaction regions defined, but, as
        # far as I can tell, no triggers. it appears to be a copy of D0101 with the triggers removed. still, I should
        # check the code to see if I'm missing something.
        for interactable, trigger in zip_longest(module.layout.interactables, module.triggers.triggers):
            if interactable is None:
                break  # we can handle an interactable without a trigger, but not a trigger without an interactable
            object_name = f'trigger_{len(self.triggers)}_{room_id}'
            trigger_object = TriggerObject(object_name, interactable, trigger)
            trigger_object.position.game_y += 3
            trigger_object.add_to_scene(self.trigger_node)
            self.triggers.append(trigger_object)

        for entrance_set in module.entrances:
            self.entrance_sets.append(entrance_set.entrances)
        if len(self.entrance_sets) > 0:
            self.set_entrance_set(0)

        self.num_bgs = len(module.backgrounds)
        for i, camera in enumerate(module.layout.cameras):
            object_name = f'camera_{len(self.cameras)}_{room_id}'
            backgrounds = [background_set.backgrounds[i] for background_set in module.backgrounds]
            camera_object = CameraObject(object_name, camera, backgrounds, self.base.loader)
            camera_object.add_to_scene(self.camera_node)
            self.cameras.append(camera_object)
            for background in backgrounds:
                if background.index >= 0 and background.index not in self.loaded_tims:
                    path = self.stage_backgrounds[self.current_stage][background.index].path
                    with path.open('rb') as f:
                        db = TimDb.read(f, fmt=TimDb.Format.from_extension(path.suffix))
                    self.loaded_tims[background.index] = db

        for layout_set in module.actor_layouts:
            self.actor_layouts.extend(layout_set.layouts)
        if len(self.actor_layouts) > 0:
            self.set_actor_layout(0)

        self.set_camera_view(None)

    def setup_window(self):
        super().setup_window()

        picker_node_path = self.camera.attachNewNode(self.picker_node)
        self.collision_traverser.addCollider(picker_node_path, self.collision_queue)

        # we use this plane when dragging to detect the point where the mouse has dragged to
        self.horizontal_node_path = self.render_target.attachNewNode(CollisionNode('room_viewport_horizontal'))
        self.horizontal_node_path.node().addSolid(self.horizontal_plane)

        self.base.taskMgr.add(self.move_camera, 'room_viewport_move')

    def watch_mouse(self, _) -> int:
        if not self.has_focus:
            return Task.cont

        is_mouse1_down = self.base.mouseWatcherNode.isButtonDown(MouseButton.one())
        if is_mouse1_down and not self.was_mouse1_down_last_frame:
            mouse_pos = self.base.mouseWatcherNode.getMouse()
            self.picker_ray.setFromLens(self.camera.node(), mouse_pos.getX(), mouse_pos.getY())
            self.collision_traverser.traverse(self.render_target)
            if self.collision_queue.getNumEntries() > 0:
                self.collision_queue.sortEntries()
                for entry in self.collision_queue.entries:
                    node_path = entry.getIntoNodePath()
                    if not node_path.isHidden() and (object_name := node_path.getNetTag('object_name')):
                        if self.selected_item is None or self.selected_item[0].name != object_name:
                            for listener in self.select_listeners:
                                listener(object_name)
                        self.was_mouse1_down_last_frame = is_mouse1_down
                        self.was_dragging_last_frame = False
                        return Task.cont

        return super().watch_mouse(_)

    def move_camera(self, task: Task) -> int:
        if not self.has_focus:
            self.last_key_time = task.time
            return Task.cont

        if self.base.mouseWatcherNode.isButtonDown(KeyboardButton.asciiKey('w')):
            y = 1.
        elif self.base.mouseWatcherNode.isButtonDown(KeyboardButton.asciiKey('s')):
            y = -1.
        else:
            y = 0.

        if self.base.mouseWatcherNode.isButtonDown(KeyboardButton.asciiKey('a')):
            x = -1.
        elif self.base.mouseWatcherNode.isButtonDown(KeyboardButton.asciiKey('d')):
            x = 1.
        else:
            x = 0.

        if x != 0. or y != 0.:
            if self.base.mouseWatcherNode.isButtonDown(KeyboardButton.shift()):
                mult = 2.
            elif self.base.mouseWatcherNode.isButtonDown(KeyboardButton.control()):
                mult = 0.5
            else:
                mult = 1.

            move_amount = mult * self.MOVE_PER_SECOND * (task.time - self.last_key_time)
            self.camera.setX(self.camera, x * move_amount)
            self.camera.setY(self.camera, y * move_amount)

        self.last_key_time = task.time
        return Task.cont

    def set_active(self, is_active: bool):
        super().set_active(is_active)
        for animation in self.actor_animations:
            if is_active:
                animation.play()
            else:
                animation.pause()

    def resize(self, width: int, height: int, keep_aspect_ratio: bool = False):
        super().resize(width, height, keep_aspect_ratio)
        self.update_camera_view()


class RoomTab(Tab):
    """Tab for inspecting and editing rooms in the game"""

    def __init__(self, project: Project, base: ShowBase):
        super().__init__('Room', project)
        self.base = base
        self.changed_room_ids = set()
        self.current_room = None
        self.detail_widget = None
        self.menu_item = None
        self.rooms = []
        self.visibility = {'colliders': True, 'cuts': True, 'triggers': True, 'cameras': True, 'actors': True,
                           'entrances': True}

        key_items = list(self.project.get_items(True))
        self.item_names = [f'Unused #{i}' for i in range(len(key_items))]
        for item in key_items:
            self.item_names[item.id] = item.name

        self.group_menu = tk.Menu(self, tearoff=False)
        self.group_menu.add_command(label='Hide', command=self.toggle_current_group)

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
                self.tree.insert(stage, tk.END, text=f'#{room.module_id:02X}: {room.name}', iid=iid)

                actor_iid = f'actors_{room_id}'
                self.tree.insert(iid, tk.END, text='Actors', iid=actor_iid, open=True)
                collider_iid = f'colliders_{room_id}'
                self.tree.insert(iid, tk.END, text='Colliders', iid=collider_iid)
                entrance_iid = f'entrances_{room_id}'
                self.tree.insert(iid, tk.END, text='Entrances', iid=entrance_iid)
                camera_iid = f'cameras_{room_id}'
                self.tree.insert(iid, tk.END, text='Cameras', iid=camera_iid)
                cut_iid = f'cuts_{room_id}'
                self.tree.insert(iid, tk.END, text='Cuts', iid=cut_iid)
                trigger_iid = f'triggers_{room_id}'
                self.tree.insert(iid, tk.END, text='Triggers', iid=trigger_iid)

        self.viewport = RoomViewport(self.base, 1024, 768, self.project, self)
        self.viewport.on_select(self.on_viewport_select)

        viewport_options = ttk.Frame(self)
        self.view_var = tk.StringVar(self, 'None')
        view_label = ttk.Label(viewport_options, text='View: ', anchor=tk.W)
        self.view_select = ttk.OptionMenu(viewport_options, self.view_var, self.view_var.get(), 'None')
        # do this after creating the OptionMenu so it doesn't trigger immediately
        self.view_var.trace_add('write', self.select_view)

        self.tree.grid(row=0, column=0, rowspan=2, sticky=tk.NS + tk.W)
        scroll.grid(row=0, column=1, rowspan=2, sticky=tk.NS)
        self.viewport.grid(row=0, column=3, sticky=tk.NS + tk.E)
        viewport_options.grid(row=1, column=3, sticky=tk.EW + tk.S)

        view_label.pack(padx=10, side=tk.LEFT)
        self.view_select.pack(side=tk.LEFT)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(3, weight=1)

        self.tree.bind('<<TreeviewSelect>>', self.select_item)
        self.tree.bind('<Button-3>', self.handle_right_click)
        self.bind('<Configure>', self.resize_3d)

    def on_viewport_select(self, identifier: str):
        self.tree.selection_set(identifier)
        self.tree.see(identifier)

    def on_update_actor(self, actor: ActorObject):
        layout_id, actor_id = self.viewport.update_actor(actor)
        iid = f'layout_{layout_id}_actor_{actor_id}_{self.current_room}'
        if actor.model:
            text = f'#{actor_id}: {actor.model.name}'
        else:
            text = 'None'
        self.tree.item(iid, text=text)

    def select_view(self, *_):
        view_name = self.view_var.get()
        if view_name == 'None':
            view = None
        else:
            camera_id = int(view_name.rsplit('#', 1)[1])
            view = self.viewport.cameras[camera_id]
        self.viewport.set_camera_view(view)

    def resize_3d(self, _=None):
        self.update()
        x, y, width, height = self.grid_bbox(3, 0, 3, 0)
        self.viewport.resize(width, height, True)

    @staticmethod
    def _update_collider(colliders: list[RectangleCollider | TriangleCollider | CircleCollider],
                         collider: RectangleCollider | TriangleCollider | CircleCollider,
                         index: int) -> bool:
        if index >= len(colliders):
            colliders.append(collider)
            return True
        if colliders[index] != collider:
            colliders[index] = collider
            return True
        return False

    def update_room(self,
                    object_type: Literal['all', 'collider', 'entrance', 'actor', 'camera', 'cut', 'trigger'] = 'all'):
        if self.current_room is not None:
            # push changes back to the room module
            changed = False
            i_rect = 0
            i_tri = 0
            i_circle = 0
            room = self.rooms[self.current_room]

            if object_type in ['all', 'collider']:
                for i, collider in enumerate(self.viewport.colliders):
                    match collider:
                        case RectangleColliderObject():
                            collider_type = ColliderType.WALL if collider.is_wall else ColliderType.RECTANGLE
                            collider_changed = self._update_collider(room.layout.rectangle_colliders,
                                                                     collider.as_collider(), i_rect)
                            i_rect += 1
                        case TriangleColliderObject():
                            collider_type = ColliderType.TRIANGLE
                            collider_changed = self._update_collider(room.layout.triangle_colliders,
                                                                     collider.as_collider(), i_tri)
                            i_tri += 1
                        case CircleColliderObject():
                            collider_type = ColliderType.CIRCLE
                            collider_changed = self._update_collider(room.layout.circle_colliders,
                                                                     collider.as_collider(), i_circle)
                            i_circle += 1
                        case _:
                            raise ValueError(f'Unexpected collider {collider}')

                    if i >= len(room.layout.colliders):
                        collider_changed = True
                        room.layout.colliders.append(Collider(collider_type, 0, collider_type.unknown))
                    elif room.layout.colliders[i].type != collider_type:
                        collider_changed = True
                        room.layout.colliders[i].type = collider_type
                        room.layout.colliders[i].unknown = collider_type.unknown

                    if collider_changed:
                        changed = True
                        iid = f'collider_{i}_{self.current_room}'
                        self.tree.item(iid, text=f'* #{i}')
                # if we have fewer colliders than we started with, delete the rest
                num_colliders = len(self.viewport.colliders)
                if num_colliders < len(room.layout.colliders):
                    changed = True
                    del room.layout.colliders[num_colliders:]

            if object_type in ['all', 'entrance']:
                entrance_set_id = self.viewport.current_entrance_set
                entrance_set = room.entrances[entrance_set_id]
                for i, entrance in enumerate(self.viewport.entrances):
                    raw_entrance = entrance.as_entrance()
                    if entrance_set.entrances[i] != raw_entrance:
                        changed = True
                        entrance_set.entrances[i] = raw_entrance
                        iid = f'entrance-set_{entrance_set_id}_entrance_{i}_{self.current_room}'
                        self.tree.item(iid, text=f'* #{i}')

            if object_type in ['all', 'actor']:
                actor_layout_id = self.viewport.current_layout
                set_index = 0
                layout_index = actor_layout_id
                for layout_set in room.actor_layouts:
                    if layout_index >= len(layout_set.layouts):
                        layout_index -= len(layout_set.layouts)
                        set_index += 1
                    else:
                        break

                layout = room.actor_layouts[set_index].layouts[layout_index]
                for i, actor in enumerate(self.viewport.actors):
                    instance = actor.as_actor_instance()
                    if layout.actors[i] != instance:
                        changed = True
                        layout.actors[i] = instance
                        iid = f'layout_{actor_layout_id}_actor_{i}_{self.current_room}'
                        self.tree.item(iid, text=f'* #{i}: {actor.model.name}' if actor.model else '* None')

            if object_type in ['all', 'camera']:
                for i, camera in enumerate(self.viewport.cameras):
                    raw_camera = camera.as_camera()
                    camera_changed = False
                    if i >= len(room.layout.cameras):
                        camera_changed = True
                        room.layout.cameras.append(raw_camera)
                    elif room.layout.cameras[i] != raw_camera:
                        camera_changed = True
                        room.layout.cameras[i] = raw_camera

                    if camera_changed:
                        changed = True
                        iid = f'camera_{i}_{self.current_room}'
                        self.tree.item(iid, text=f'* #{i}')

                num_cameras = len(self.viewport.cameras)
                if num_cameras < len(room.layout.cameras):
                    changed = True
                    del room.layout.cameras[num_cameras:]

            if object_type in ['all', 'cut']:
                for i, cut in enumerate(self.viewport.cuts):
                    raw_cut = cut.as_camera_cut()
                    cut_changed = False
                    if i >= len(room.layout.cuts):
                        cut_changed = True
                        room.layout.cuts.append(raw_cut)
                    elif room.layout.cuts[i] != raw_cut:
                        room.layout.cuts[i] = raw_cut

                    if cut_changed:
                        changed = True
                        iid = f'cut_{i}_{self.current_room}'
                        self.tree.item(iid, text=f'* #{i}')

                num_cuts = len(self.viewport.cuts)
                if num_cuts < len(room.layout.cuts):
                    changed = True
                    del room.layout.cuts[num_cuts:]

            if object_type in ['all', 'trigger']:
                # we don't support adding triggers, because although the interactables would support it, we can't
                # guarantee the triggers would
                for i, trigger in enumerate(self.viewport.triggers):
                    interactable, raw_trigger = trigger.as_interactable()
                    trigger_changed = False
                    if room.layout.interactables[i] != interactable:
                        trigger_changed = True
                        room.layout.interactables[i] = interactable
                    if raw_trigger is not None and room.triggers.triggers[i] != raw_trigger:
                        trigger_changed = True
                        room.triggers.triggers[i] = raw_trigger

                    if trigger_changed:
                        changed = True
                        iid = f'trigger_{i}_{self.current_room}'
                        self.tree.item(iid, text=f'* #{i}')

                num_triggers = len(self.viewport.triggers)
                if num_triggers < len(room.layout.interactables):
                    changed = True
                    del room.layout.interactables[num_triggers:]
                if num_triggers < len(room.triggers.triggers):
                    changed = True
                    del room.triggers.triggers[num_triggers:]

            room.validate_for_write()

            if changed:
                self.changed_room_ids.add(self.current_room)
                iid = f'room_{self.current_room}'
                self.tree.item(iid, text=f'* #{room.module_id:02X}: {room.name}')

    def set_room(self, room_id: int):
        if self.current_room != room_id:
            self.update_room()

            self.current_room = room_id
            self.viewport.set_room(self.rooms[room_id], room_id)

            # update selectable views
            self.view_var.set('None')
            menu = self.view_select['menu']
            menu.delete(1, 'end')
            for i in range(len(self.viewport.cameras)):
                label = f'Camera #{i}'
                menu.add_command(label=label, command=lambda value=label: self.view_var.set(value))

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
        room_level_ids = ['room', 'actors', 'colliders', 'cameras', 'cuts', 'triggers', 'entrances']
        object_ids = ['collider', 'trigger', 'cut', 'camera']
        if any(iid.startswith(f'{room_level_id}_') for room_level_id in room_level_ids):
            room_id = int(iid.split('_')[1])
            if self.current_room != room_id:
                self.set_room(room_id)
                self.add_children(room_id, 'collider', self.viewport.colliders)
                iid = f'entrances_{room_id}'
                if not self.tree.get_children(iid):
                    for i, entrance_set in enumerate(self.viewport.entrance_sets):
                        set_iid = f'entrance-set_{i}_{room_id}'
                        self.tree.insert(iid, tk.END, text=f'Set #{i}', iid=set_iid)
                        for j, entrance in enumerate(entrance_set):
                            entrance_iid = f'entrance-set_{i}_entrance_{j}_{room_id}'
                            self.tree.insert(set_iid, tk.END, text=f'#{j}', iid=entrance_iid)
                self.add_children(room_id, 'cut', self.viewport.cuts)
                self.add_children(room_id, 'trigger', self.viewport.triggers)
                self.add_children(room_id, 'camera', self.viewport.cameras)
                iid = f'actors_{room_id}'
                if not self.tree.get_children(iid):
                    for i, layout in enumerate(self.viewport.actor_layouts):
                        layout_iid = f'layout_{i}_{room_id}'
                        self.tree.insert(iid, tk.END, text=f'Layout #{i}: {layout.name}', iid=layout_iid)
                        for j, actor_instance in enumerate(layout.actors):
                            actor_iid = f'layout_{i}_actor_{j}_{room_id}'
                            if actor_instance.type < 0:
                                name = 'None'
                            else:
                                model_name = self.viewport.actor_models[actor_instance.type].name
                                name = f'#{actor_instance.id}: {model_name}'
                            self.tree.insert(layout_iid, tk.END, text=name, iid=actor_iid)
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
                    editor = CameraEditor(obj, self.viewport.num_bgs, self.viewport.current_bg, self.viewport.select_bg,
                                          self.viewport.update_camera_view, self)
                case _:
                    editor = obj = None
            self.set_detail_widget(editor)
            self.viewport.select(obj)
            if camera_view is not None:
                self.viewport.set_camera_view(camera_view)
        elif iid.startswith('entrance-set_'):
            pieces = iid.split('_')
            set_id = int(pieces[1])
            room_id = int(pieces[-1])
            self.set_room(room_id)
            self.update_room('entrance')
            self.viewport.set_entrance_set(set_id)
            if pieces[2] == 'entrance':
                entrance_id = int(pieces[3])
                entrance = self.viewport.entrances[entrance_id]
                self.set_detail_widget(EntranceEditor(entrance, self))
                self.viewport.select(entrance)
                self.viewport.set_camera_view(None)
        elif iid.startswith('layout_'):
            pieces = iid.split('_')
            layout_id = int(pieces[1])
            room_id = int(pieces[-1])
            self.set_room(room_id)
            self.update_room('actor')
            self.viewport.set_actor_layout(layout_id)
            if pieces[2] == 'actor':
                actor_id = int(pieces[3])
                actor = self.viewport.actors[actor_id]
                self.set_detail_widget(ActorEditor(actor, self.viewport.actor_models, self.on_update_actor, self))
                self.viewport.select(actor)

    def set_active(self, is_active: bool):
        self.viewport.set_active(is_active)
        if is_active:
            self.resize_3d()

    @property
    def has_unsaved_changes(self) -> bool:
        return len(self.changed_room_ids) > 0
