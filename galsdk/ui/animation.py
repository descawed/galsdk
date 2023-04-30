import numpy as np
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import LQuaternionf, NodePath

from galsdk import util
from galsdk.animation import Animation
from galsdk.coords import Point


class ActiveAnimation:
    def __init__(self, base: ShowBase, name: str, model: NodePath, animation: Animation):
        self.base = base
        self.name = name
        self.model = model
        self.animation = animation
        # +1 so we actually show the last frame for a moment
        self.duration = Animation.FRAME_TIME * (len(animation.frames) + 1)
        self.is_playing = False
        self.last_time = 0.
        self.frame_time = 0.
        self.task = base.taskMgr.add(self.animate, name)
        self.nodes = {}
        for node in self.model.findAllMatches('**/=index'):
            index = int(node.getTag('index'))
            self.nodes[index] = node

    def play(self):
        self.is_playing = True

    def pause(self):
        self.is_playing = False

    def remove(self):
        self.base.taskMgr.remove(self.task)
        self.task = None
        self.model.setPos(0, 0, 0)
        for node in self.nodes.values():
            node.setHpr(0, 0, 0)

    def animate(self, task: Task):
        if self.is_playing:
            self.frame_time += task.time - self.last_time
            if self.frame_time > self.duration:
                self.frame_time -= self.duration
            frame_index = int(self.frame_time / Animation.FRAME_TIME)
            interp_amount = (self.frame_time % Animation.FRAME_TIME) / Animation.FRAME_TIME
            if frame_index < len(self.animation.frames):
                if frame_index < len(self.animation.frames) - 1:
                    this_translation = Point(*self.animation.frames[frame_index].translation)
                    next_translation = Point(*self.animation.frames[frame_index + 1].translation)
                    this_tnp = np.array([this_translation.panda_x, this_translation.panda_y, this_translation.panda_z])
                    next_tnp = np.array([next_translation.panda_x, next_translation.panda_y, next_translation.panda_z])
                    translation = util.interpolate(interp_amount, this_tnp, next_tnp)

                    this_rotations = self.animation.convert_frame(frame_index)[1]
                    next_rotations = self.animation.convert_frame(frame_index + 1)[1]
                    rotations = []
                    for this_rotation, next_rotation in zip(this_rotations, next_rotations, strict=True):
                        rotations.append(util.interpolate(interp_amount, this_rotation, next_rotation))
                else:
                    point = Point(*self.animation.frames[frame_index].translation)
                    translation = np.array([point.panda_x, point.panda_y, point.panda_z])
                    rotations = self.animation.convert_frame(frame_index)[1]

                self.model.setPos(*translation)
                for i, rotation in enumerate(rotations):
                    # convert to panda coordinates
                    panda_rot = np.array([-rotation[0], rotation[2], rotation[1]])
                    half_rads = panda_rot / 2
                    cx, cy, cz = np.cos(half_rads)
                    sx, sy, sz = np.sin(half_rads)
                    qx = np.array([sx, 0., 0., cx], np.float32)
                    qy = np.array([0., sy, 0., cy], np.float32)
                    qz = np.array([0., 0., sz, cz], np.float32)
                    # still need to order the rotations as the game would
                    quaternion = util.quat_mul(qx, util.quat_mul(qz, qy))
                    norm = np.linalg.norm(quaternion)
                    if norm != 0:
                        quaternion /= norm
                    panda_quat = LQuaternionf(quaternion[3], quaternion[0], quaternion[1], quaternion[2])
                    self.nodes[i].setQuat(panda_quat)

        self.last_time = task.time
        return Task.cont
