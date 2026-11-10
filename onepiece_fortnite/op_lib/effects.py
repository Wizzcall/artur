"""
Particle-style effects, all keyframed (deterministic, render-farm safe,
no particle cache to bake):
  motes()        glowing energy particles drifting / rising
  light_rays()   rotating cone beams (god rays)
  shock_ring()   expanding glowing ring
  burst()        radial explosion of sparks
  slash_arcs()   Zoro sword slashes
  lightning()    Nami lightning bolts
  flames()       Sanji fire around a limb
  sparkles()     Chopper star sparkles
  treasure_rain() V-Bucks / tokens / symbols raining from the sky
  point_flash()  light pulse
"""
import math
import random
import bpy
import bmesh
from mathutils import Vector, Euler

import config as C
from .utils import (empty, obj_from_mesh, mesh_ico, mesh_cylinder, mesh_torus, mesh_plane, link,
                    mat_emit_fade, mat_beam, key, key_loc, key_rot, key_scale, key_alpha,
                    no_shadow, only_camera_visible)

R = math.radians
RNG = random.Random(C.SEED)


def _fx_obj(name, me, mat, parent=None, loc=(0, 0, 0), rot=(0, 0, 0)):
    ob = obj_from_mesh(name, me, mat, parent, loc, rot)
    ob.color = (1, 1, 1, 0)
    no_shadow(ob)
    for a in ("visible_diffuse", "visible_glossy"):
        setattr(ob, a, False)
    return ob


def _hide_outside(ob, f0, f1):
    """Render-hide an FX object outside [f0, f1] (saves render time)."""
    key(ob, "hide_render", max(1, f0 - 1), False if f0 <= 1 else True, "CONSTANT")
    key(ob, "hide_render", f0, False, "CONSTANT")
    key(ob, "hide_render", f1 + 1, True, "CONSTANT")


# ---------------------------------------------------------------------
def motes(name, center, radius, count, f0, f1, color, rise=3.0, size=0.04,
          strength=8.0, parent=None, swirl=0.0, height=0.0):
    """Glowing dots drifting upward around `center` (with optional swirl)."""
    mat = mat_emit_fade(f"{name}_Mat", color, strength)
    me = mesh_ico(f"{name}_mesh", size, 1)
    obs = []
    for i in range(count):
        a = RNG.uniform(0, 2 * math.pi)
        r = radius * math.sqrt(RNG.uniform(0.05, 1))
        z0 = RNG.uniform(-0.3, height)
        p0 = Vector(center) + Vector((math.cos(a) * r, math.sin(a) * r, z0))
        ob = _fx_obj(f"{name}{i}", me, mat, parent, p0)
        life = RNG.randint(int((f1 - f0) * 0.4), max(int((f1 - f0) * 0.4) + 1, f1 - f0))
        s = RNG.randint(f0, max(f0, f1 - life))
        e = s + life
        a2 = a + swirl * RNG.uniform(0.6, 1.4)
        r2 = r * RNG.uniform(0.8, 1.3)
        p1 = Vector(center) + Vector((math.cos(a2) * r2, math.sin(a2) * r2,
                                      z0 + rise * RNG.uniform(0.6, 1.4)))
        steps = 4
        for k in range(steps + 1):
            t = k / steps
            aa = a + (a2 - a) * t
            rr = r + (r2 - r) * t
            p = Vector(center) + Vector((math.cos(aa) * rr, math.sin(aa) * rr, z0 + (p1.z - z0) * t))
            key_loc(ob, int(s + (e - s) * t), p, "LINEAR")
        sc = RNG.uniform(0.6, 1.5)
        ob.scale = (sc, sc, sc)
        key_alpha(ob, s, 0.0, "LINEAR")
        key_alpha(ob, s + max(3, life // 5), 1.0, "LINEAR")
        key_alpha(ob, e - max(3, life // 4), 1.0, "LINEAR")
        key_alpha(ob, e, 0.0, "LINEAR")
        _hide_outside(ob, s, e)
        obs.append(ob)
    return obs


def light_rays(name, center, count, f0, f1, color, length=14, width=0.6, strength=3.0,
               spin=60, parent=None, axis_rot=(0, 0, 0), fan=360, peak=1.0):
    """Sunburst of cone beams in the root's local XZ plane (faces +/-Y,
    i.e. the camera in most shots), spinning around local Y.
    Narrow tip at `center`, beams fade outward."""
    from mathutils import Matrix
    root = empty(name, parent, center, axis_rot)
    spinner = empty(f"{name}_spin", root)
    mat = mat_beam(f"{name}_Mat", color, strength)
    for i in range(count):
        L = length * RNG.uniform(0.6, 1.1)
        me = mesh_cylinder(f"{name}_m{i}", width * RNG.uniform(0.4, 1.2), L, 16, r2=0.02)
        me.transform(Matrix.Rotation(math.pi, 4, "X"))     # wide end up
        me.transform(Matrix.Translation((0, 0, L / 2)))    # tip at origin
        step = fan / (count if fan >= 360 else max(1, count - 1))
        ang = R(-fan / 2 + step * (i + RNG.uniform(-0.3, 0.3))) if fan < 360 else R(step * (i + RNG.uniform(-0.3, 0.3)))
        ob = _fx_obj(f"{name}{i}", me, mat, spinner, (0, 0, 0), (0, ang, 0))
        only_camera_visible(ob)
        k = RNG.uniform(0.6, 1.0) * peak
        key_alpha(ob, f0, 0.0)
        key_alpha(ob, f0 + 12, k)
        for f in range(f0 + 12, f1 - 12, 9):          # flicker
            key_alpha(ob, f, k * RNG.uniform(0.6, 1.0))
        key_alpha(ob, f1 - 10, k * 0.8)
        key_alpha(ob, f1, 0.0)
        _hide_outside(ob, f0, f1)
    key_rot(spinner, f0, (0, 0, 0), "LINEAR")
    key_rot(spinner, f1, (0, R(spin), 0), "LINEAR")
    return root


def shock_ring(name, loc, f0, color, r_end=8, dur=14, thick=0.08, strength=12, parent=None,
               rot=(0, 0, 0)):
    mat = mat_emit_fade(f"{name}_Mat", color, strength)
    me = mesh_torus(f"{name}_mesh", 1.0, thick, 64, 8)
    ob = _fx_obj(name, me, mat, parent, loc, rot)
    only_camera_visible(ob)
    key_scale(ob, f0, 0.05, "EXPO")
    key_scale(ob, f0 + dur, r_end, "LINEAR")
    key_alpha(ob, f0 - 1, 0.0, "CONSTANT")
    key_alpha(ob, f0, 1.0, "LINEAR")
    key_alpha(ob, f0 + dur, 0.0, "LINEAR")
    _hide_outside(ob, f0, f0 + dur)
    return ob


def burst(name, loc, f0, color, count=40, speed=6.0, dur=24, size=0.022, gravity=-4.0,
          strength=10, parent=None, stretch=4.0):
    """Explosion of elongated sparks flying outward."""
    mat = mat_emit_fade(f"{name}_Mat", color, strength)
    me = mesh_ico(f"{name}_mesh", size, 1)
    p0 = Vector(loc)
    for i in range(count):
        d = Vector((RNG.uniform(-1, 1), RNG.uniform(-1, 1), RNG.uniform(-0.6, 1))).normalized()
        v = d * speed * RNG.uniform(0.5, 1.2)
        ob = _fx_obj(f"{name}{i}", me, mat, parent, p0)
        ob.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
        ob.scale = (1, 1, stretch)
        n = 4
        for k in range(n + 1):
            t = dur / C.FPS * k / n
            p = p0 + v * t + Vector((0, 0, 0.5 * gravity * t * t))
            key_loc(ob, int(f0 + dur * k / n), p, "LINEAR" if k else "EXPO")
        key_alpha(ob, f0 - 1, 0.0, "CONSTANT")
        key_alpha(ob, f0, 1.0, "LINEAR")
        key_alpha(ob, f0 + int(dur * 0.6), 0.8, "LINEAR")
        key_alpha(ob, f0 + dur, 0.0, "LINEAR")
        _hide_outside(ob, f0, f0 + dur)


def point_flash(name, loc, f0, color, peak=3000, dur=12, parent=None, radius=1.0):
    ld = bpy.data.lights.new(name, "POINT")
    ld.color = color
    ld.shadow_soft_size = radius
    ob = bpy.data.objects.new(name, ld)
    link(ob)
    ob.parent = parent
    ob.location = loc
    ld.energy = 0
    ld.keyframe_insert("energy", frame=f0 - 1)
    ld.energy = peak
    ld.keyframe_insert("energy", frame=f0 + 2)
    ld.energy = 0
    ld.keyframe_insert("energy", frame=f0 + dur)
    return ob


# ---------------------------------------------------------------------
# Character-specific effects
# ---------------------------------------------------------------------
def slash_arcs(name, loc, f0, color, parent=None, n=3):
    """Zoro: green crescent slashes that sweep and fade."""
    mat = mat_emit_fade(f"{name}_Mat", color, 14)
    for i in range(n):
        me = mesh_torus(f"{name}_m{i}", 0.9 + 0.25 * i, 0.035, 40, 6, arc=R(150))
        rot = (R(90 + RNG.uniform(-50, 50)), R(RNG.uniform(-40, 40)), R(RNG.uniform(0, 360)))
        ob = _fx_obj(f"{name}{i}", me, mat, parent, loc, rot)
        only_camera_visible(ob)
        ob.scale = (1, 1, 0.3)
        s = f0 + i * 3
        e = Euler(rot)
        key_rot(ob, s, rot, "EXPO")
        key_rot(ob, s + 12, (e.x, e.y, e.z + R(220)), "LINEAR")
        key_scale(ob, s, (0.4, 0.4, 0.3), "EXPO")
        key_scale(ob, s + 12, (1.6, 1.6, 0.3), "LINEAR")
        key_alpha(ob, s - 1, 0.0, "CONSTANT")
        key_alpha(ob, s, 1.0, "LINEAR")
        key_alpha(ob, s + 14, 0.0, "LINEAR")
        _hide_outside(ob, s, s + 14)


def _bolt_curve(name, start, end, segs=9, jitter=0.35, bevel=0.025):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = bevel
    cu.bevel_resolution = 1
    sp = cu.splines.new("POLY")
    sp.points.add(segs)
    a, b = Vector(start), Vector(end)
    for i, p in enumerate(sp.points):
        t = i / segs
        q = a.lerp(b, t)
        if 0 < i < segs:
            q += Vector((RNG.uniform(-1, 1), RNG.uniform(-1, 1), RNG.uniform(-1, 1))) * jitter
        p.co = (*q, 1)
    return cu


def lightning(name, center, f0, color, parent=None, n=5, dur=30, height=4.0, bevel=0.025,
              jitter=0.35, spread=1.0, strength=25):
    """Nami: bolts striking down around her, flickering on/off."""
    mat = mat_emit_fade(f"{name}_Mat", color, strength)
    c = Vector(center)
    for i in range(n):
        a = 2 * math.pi * i / n + RNG.uniform(-0.3, 0.3)
        r = RNG.uniform(0.6, 1.3) * spread
        end = c + Vector((math.cos(a) * r, math.sin(a) * r, 0))
        start = end + Vector((RNG.uniform(-0.6, 0.6) * spread, RNG.uniform(-0.6, 0.6) * spread, height))
        cu = _bolt_curve(f"{name}_c{i}", start, end, segs=12, jitter=jitter, bevel=bevel)
        cu.materials.append(mat)
        ob = bpy.data.objects.new(f"{name}{i}", cu)
        link(ob)
        ob.parent = parent
        ob.color = (1, 1, 1, 0)
        only_camera_visible(ob)
        s = f0 + RNG.randint(0, dur // 2)
        key_alpha(ob, s - 1, 0.0, "CONSTANT")
        for k in range(6):
            key_alpha(ob, s + k * 2, 1.0 if k % 2 == 0 else 0.15, "CONSTANT")
        key_alpha(ob, s + 12, 0.0, "CONSTANT")
        _hide_outside(ob, s, s + 12)


def flames(name, parent, f0, f1, color=(1.0, 0.35, 0.05), length=0.9, count=10, offset=(0, 0, 0)):
    """Sanji: fire tongues along a limb (parent = knee/shin pivot,
    limb direction = local -Z)."""
    mat_core = mat_emit_fade(f"{name}_Core", (1.0, 0.75, 0.2), 18)
    mat_out = mat_emit_fade(f"{name}_Outer", color, 12)
    root = empty(name, parent, offset)
    for i in range(count):
        t = i / (count - 1)
        me = mesh_cylinder(f"{name}_m{i}", 0.09, 0.45, 10, r2=0.0)
        me.transform(__import__("mathutils").Matrix.Translation((0, 0, 0.2)))
        ob = _fx_obj(f"{name}{i}", me, mat_core if i % 3 == 0 else mat_out, root,
                     (RNG.uniform(-0.05, 0.05), RNG.uniform(-0.05, 0.05), -length * t),
                     (R(RNG.uniform(-40, 40)), R(RNG.uniform(-40, 40)), 0))
        only_camera_visible(ob)
        key_alpha(ob, f0 - 1, 0.0, "CONSTANT")
        key_alpha(ob, f0, 1.0, "LINEAR")
        for f in range(f0, f1, 3):
            s = RNG.uniform(0.6, 1.5)
            key_scale(ob, f, (s * 0.8, s * 0.8, s * RNG.uniform(0.9, 1.8)), "LINEAR")
        key_alpha(ob, f1 - 6, 1.0, "LINEAR")
        key_alpha(ob, f1, 0.0, "LINEAR")
        _hide_outside(ob, f0, f1)
    # warm light
    ld = bpy.data.lights.new(f"{name}_light", "POINT")
    ld.color = color
    lo = bpy.data.objects.new(f"{name}_light", ld)
    link(lo)
    lo.parent = root
    lo.location = (0, 0.3, -length / 2)
    for f in range(f0 - 1, f1 + 1, 3):
        ld.energy = 0 if f < f0 or f >= f1 else RNG.uniform(80, 160)
        ld.keyframe_insert("energy", frame=f)
    ld.energy = 0
    ld.keyframe_insert("energy", frame=f1 + 1)
    return root


def _star_mesh(name, r_out=0.12, r_in=0.05, depth=0.03):
    bm = bmesh.new()
    pts = []
    for i in range(10):
        a = math.pi / 2 + i * math.pi / 5
        r = r_out if i % 2 == 0 else r_in
        pts.append((math.cos(a) * r, math.sin(a) * r))
    top = [bm.verts.new((x, y, depth)) for x, y in pts]
    bot = [bm.verts.new((x, y, -depth)) for x, y in pts]
    bm.faces.new(top)
    bm.faces.new(list(reversed(bot)))
    for i in range(10):
        j = (i + 1) % 10
        bm.faces.new((top[i], bot[i], bot[j], top[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def sparkles(name, center, f0, color, count=26, parent=None, radius=1.6, dur=40):
    """Chopper: cute pink / white stars popping and twinkling."""
    mats = [mat_emit_fade(f"{name}_MatA", color, 10), mat_emit_fade(f"{name}_MatB", (1, 1, 1), 10)]
    me = _star_mesh(f"{name}_mesh")
    c = Vector(center)
    for i in range(count):
        d = Vector((RNG.uniform(-1, 1), RNG.uniform(-0.3, 0.6), RNG.uniform(-0.2, 1))).normalized()
        p1 = c + d * radius * RNG.uniform(0.5, 1.2)
        ob = _fx_obj(f"{name}{i}", me, mats[i % 2], parent, c, (R(90), 0, 0))
        only_camera_visible(ob)
        s = f0 + RNG.randint(0, 6)
        e = s + RNG.randint(dur // 2, dur)
        key_loc(ob, s, c, "EXPO")
        key_loc(ob, s + 10, p1, "BEZIER")
        key_loc(ob, e, p1 + Vector((0, 0, 0.4)), "LINEAR")
        sc = RNG.uniform(0.6, 1.4)
        key_scale(ob, s, 0.01, "BACK")
        key_scale(ob, s + 8, sc, "BEZIER")
        for f in range(s + 8, e, 5):                  # twinkle
            key_scale(ob, f, sc * RNG.uniform(0.5, 1.2), "BEZIER")
        key_rot(ob, s, (R(90), 0, 0), "LINEAR")
        key_rot(ob, e, (R(90), R(RNG.uniform(-200, 200)), 0), "LINEAR")
        key_alpha(ob, s - 1, 0.0, "CONSTANT")
        key_alpha(ob, s, 1.0, "LINEAR")
        key_alpha(ob, e - 6, 1.0, "LINEAR")
        key_alpha(ob, e, 0.0, "LINEAR")
        _hide_outside(ob, s, e)


# ---------------------------------------------------------------------
# Treasure rain
# ---------------------------------------------------------------------
def treasure_rain(temps, origin, f0, f1, n_vbucks=40, n_tokens=12, n_symbols=16,
                  spread=9.0, up=10.0, gravity=-7.0, seed_shift=0, area_center=None,
                  n_cards=0, n_gliders=0):
    """Items explode out of `origin` at f0 and fall with gravity until f1.
    Coins are linked duplicates of the template hierarchy (cheap)."""
    rnd = random.Random(C.SEED + seed_shift)
    o = Vector(origin)
    items = []

    def dup_tree(src, name):
        new = src.copy()
        link(new)
        new.name = name
        new.parent = None
        for ch in src.children:
            c2 = ch.copy()
            link(c2)
            c2.parent = new
        return new

    kinds = (["vbuck"] * n_vbucks) + (["token"] * n_tokens) + (["symbol"] * n_symbols) \
        + (["card"] * n_cards) + (["glider"] * n_gliders)
    rnd.shuffle(kinds)
    for i, kind in enumerate(kinds):
        if kind == "symbol":
            ob = obj_from_mesh(f"Rain_sym{i}", temps["symbol_mesh"], temps["symbol_mat"], None, o)
            ob.color = (1, 1, 1, 1)
            no_shadow(ob)
        elif kind == "card":
            ob = obj_from_mesh(f"Rain_card{i}", temps["card_mesh"], temps["card_mats"][i % 3], None, o)
            no_shadow(ob)
        else:
            ob = dup_tree(temps[kind], f"Rain_{kind}{i}")
        start = f0 + rnd.randint(0, 10)
        a = rnd.uniform(0, 2 * math.pi)
        horiz = Vector((math.cos(a), math.sin(a) * 0.8 + 0.25, 0)) * rnd.uniform(0.2, 1.0) * spread
        v = Vector((horiz.x, horiz.y, up * rnd.uniform(0.3, 1.0)))
        steps = 8
        dur = f1 - start
        g = gravity * (0.12 if kind == "glider" else (0.45 if kind == "card" else 1.0))   # floaty
        for k in range(steps + 1):
            t = dur / C.FPS * k / steps
            # air drag: slows horizontal motion over time
            p = o + Vector((v.x, v.y, 0)) * (1 - math.exp(-t * 1.2)) / 1.2 \
                + Vector((0, 0, v.z * t + 0.5 * g * t * t))
            if kind == "glider":                       # gliders keep drifting sideways
                p += Vector((math.cos(a), math.sin(a), 0)) * t * 1.2
            key_loc(ob, int(start + dur * k / steps), p, "BEZIER" if k else "EXPO")
        if kind == "glider":
            yaw = a - math.pi / 2
            key_rot(ob, start, (0, R(rnd.uniform(-15, 15)), yaw), "LINEAR")
            key_rot(ob, f1, (R(-8), R(rnd.uniform(-15, 15)), yaw + rnd.uniform(-0.6, 0.6)), "LINEAR")
        elif kind == "card":                           # cards flutter, mostly facing out
            r0 = Euler((R(90 + rnd.uniform(-25, 25)), 0, rnd.uniform(-0.5, 0.5) + math.pi))
            key_rot(ob, start, r0, "LINEAR")
            key_rot(ob, f1, (r0.x + rnd.uniform(-1.2, 1.2), rnd.uniform(-0.8, 0.8), r0.z + rnd.uniform(-2, 2)),
                    "LINEAR")
        else:
            r0 = Euler((rnd.uniform(0, 6.28), rnd.uniform(0, 6.28), rnd.uniform(0, 6.28)))
            key_rot(ob, start, r0, "LINEAR")
            key_rot(ob, f1, (r0.x + rnd.uniform(-12, 12), r0.y + rnd.uniform(-8, 8), r0.z + rnd.uniform(-6, 6)),
                    "LINEAR")
        sc = rnd.uniform(0.8, 1.3) * {"symbol": 1.4, "card": 1.5, "glider": 1.3}.get(kind, 1.0)
        key_scale(ob, start, 0.01, "BACK")
        key_scale(ob, start + 8, sc, "BEZIER")
        for x in [ob] + list(ob.children):
            key(x, "hide_render", 1, True, "CONSTANT")
            key(x, "hide_render", start, False, "CONSTANT")
            key(x, "hide_render", f1 + 1, True, "CONSTANT")
        items.append(ob)
    return items


def gentle_rain(temps, center, f0, f1, count=26, width=12, height=14, seed_shift=99):
    """Slow-falling coins in the background (finale)."""
    rnd = random.Random(C.SEED + seed_shift)
    c = Vector(center)
    for i in range(count):
        kind = "vbuck" if i % 3 else "token"
        src = temps[kind]
        ob = src.copy()
        link(ob)
        ob.name = f"Gentle_{kind}{i}"
        for ch in src.children:
            c2 = ch.copy()
            link(c2)
            c2.parent = ob
        x = c.x + rnd.uniform(-width / 2, width / 2)
        y = c.y + rnd.uniform(-6, 2)
        z0 = c.z + rnd.uniform(0, height)
        speed = rnd.uniform(1.5, 3.0)
        dur_s = (f1 - f0) / C.FPS
        key_loc(ob, f0, (x, y, z0), "LINEAR")
        key_loc(ob, f1, (x + rnd.uniform(-1, 1), y, z0 - speed * dur_s), "LINEAR")
        r0 = Euler((rnd.uniform(0, 6.28), rnd.uniform(0, 6.28), 0))
        key_rot(ob, f0, r0, "LINEAR")
        key_rot(ob, f1, (r0.x + rnd.uniform(-6, 6), r0.y + rnd.uniform(-6, 6), r0.z + 3), "LINEAR")
        ob.scale = (0.9, 0.9, 0.9)
        for x_ in [ob] + list(ob.children):
            key(x_, "hide_render", 1, True, "CONSTANT")
            key(x_, "hide_render", f0, False, "CONSTANT")


# ---------------------------------------------------------------------
# Storm rain
# ---------------------------------------------------------------------
def rain(name, center, size=(22, 22), top=11.0, f0=1, f1=240, count=320, color=(0.65, 0.75, 0.95),
         strength=1.6, wind=(0.8, -0.3), fade=20):
    """Falling rain streaks inside a box around `center`.  Each streak
    loops (fall -> jump back up) with its own speed and phase."""
    mat = mat_emit_fade(f"{name}_Mat", color, strength)
    me = mesh_cylinder(f"{name}_mesh", 0.008, 0.9, 6)
    c = Vector(center)
    w = Vector((wind[0], wind[1], 0))
    for i in range(count):
        x = c.x + RNG.uniform(-size[0] / 2, size[0] / 2)
        y = c.y + RNG.uniform(-size[1] / 2, size[1] / 2)
        period = RNG.randint(13, 19)                      # frames per fall
        fall = Vector((0, 0, -top)) + w * (period / C.FPS)
        tilt = Vector((-fall.x, -fall.y, -fall.z)).normalized().to_track_quat("Z", "Y").to_euler()
        ob = _fx_obj(f"{name}{i}", me, mat, None, (x, y, top), tilt)
        only_camera_visible(ob)
        start_top = Vector((x, y, top))
        f = f0 - RNG.randint(0, period)
        while f < f1:
            key_loc(ob, f, start_top, "LINEAR")
            key_loc(ob, f + period - 1, start_top + fall * ((period - 1) / period), "CONSTANT")
            f += period
        a = RNG.uniform(0.5, 1.0)
        key_alpha(ob, f0, a, "LINEAR")
        key_alpha(ob, f1 - fade, a, "LINEAR")
        key_alpha(ob, f1, 0.0, "LINEAR")
        _hide_outside(ob, f0, f1)
