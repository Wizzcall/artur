"""
Camera rig: one camera that tracks a target empty ("CamTarget").
Shots are authored as (frame, position, target, lens) keys:

    rig.key(f, pos, target, lens)          smooth move (ease in/out)
    rig.cut(f, pos, target, lens)          hard cut at frame f
    rig.orbit(f0, f1, center, radius, a0, a1, h0, h1)
    rig.shake(f0, f1, amp)                 handheld / impact shake

Moves: dolly (pos), orbit, rise (z), punch zoom (lens).
"""
import math
import random
import bpy
from mathutils import Vector

import config as C
from .utils import key, key_loc, link
from .hud import SENSOR


class CameraRig:
    def __init__(self):
        cd = bpy.data.cameras.new("MainCam")
        cd.sensor_fit = "VERTICAL"
        cd.sensor_height = SENSOR
        cd.lens = 30
        cd.clip_start = 0.05
        cd.clip_end = 1500
        self.cam = bpy.data.objects.new("MainCam", cd)
        link(self.cam)
        bpy.context.scene.camera = self.cam
        self.target = bpy.data.objects.new("CamTarget", None)
        link(self.target)
        # the camera body sits on a "shake" parent so shake never fights
        # with the authored path
        self.shaker = bpy.data.objects.new("CamShake", None)
        link(self.shaker)
        self.cam.parent = self.shaker
        con = self.cam.constraints.new("TRACK_TO")
        con.target = self.target
        con.track_axis = "TRACK_NEGATIVE_Z"
        con.up_axis = "UP_Y"
        self.rnd = random.Random(C.SEED + 5)
        self.last = ((0, 0, 0), (0, 1, 0), 30.0)

    # -----------------------------------------------------------------
    def key(self, f, pos, target, lens=None, interp="BEZIER"):
        lens = self.last[2] if lens is None else lens
        key_loc(self.shaker, f, pos, interp)
        key_loc(self.target, f, target, interp)
        key(self.cam.data, "lens", f, lens, interp)
        self.last = (tuple(pos), tuple(target), lens)

    def cut(self, f, pos, target, lens=None, interp="BEZIER"):
        """Hard cut: hold the previous framing until f-1 (CONSTANT key),
        then jump to the new framing at frame f."""
        p, t, l = self.last
        self.key(f - 1, p, t, l, "CONSTANT")
        self.key(f, pos, target, lens, interp)

    def orbit(self, f0, f1, center, radius, a0, a1, h0, h1, step=6, lens=None, target_offset=(0, 0, 0)):
        """Circle around `center`.  Angles in degrees, 0 = +Y (front)."""
        c = Vector(center)
        n = max(2, (f1 - f0) // step)
        for i in range(n + 1):
            t = i / n
            # smoothstep for gentle start / end
            ts = t * t * (3 - 2 * t)
            a = math.radians(a0 + (a1 - a0) * ts)
            h = h0 + (h1 - h0) * ts
            pos = c + Vector((math.sin(a) * radius, math.cos(a) * radius, h))
            f = int(round(f0 + (f1 - f0) * t))
            self.key(f, pos, c + Vector(target_offset), lens, "BEZIER")

    def shake(self, f0, f1, amp=0.08, freq=2):
        """Adds keyed jitter to the camera body (child of CamShake)."""
        key_loc(self.cam, f0 - 1, (0, 0, 0), "BEZIER")
        for f in range(f0, f1 + 1, freq):
            fall = 1 - (f - f0) / max(1, f1 - f0)
            off = Vector((self.rnd.uniform(-1, 1), self.rnd.uniform(-1, 1), self.rnd.uniform(-1, 1))) * amp * fall
            key_loc(self.cam, f, off, "BEZIER")
        key_loc(self.cam, f1 + 1, (0, 0, 0), "BEZIER")
