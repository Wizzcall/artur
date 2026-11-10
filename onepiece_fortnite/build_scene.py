"""
=====================================================================
  ONE PIECE x FORTNITE - "Pirate Shop Access"  |  MAIN BLENDER SCRIPT
=====================================================================
Builds the complete animated scene from code (no assets, no UI) and
optionally renders it.

Run with Blender in background mode:
    blender -b -P build_scene.py -- [options]
or with the `bpy` Python module (pip install bpy):
    python3 build_scene.py [options]

Options:
    --render                 render the animation (PNG frames)
    --frames 1-300           frame range to render (default: all)
    --stills 90,300,700      render only these frames (preview JPGs)
    --quality preview|draft|final   (overrides config / OPF_QUALITY)
    --no-save                don't write the .blend file

The STORYBOARD (what happens when) lives in the `direct_*` functions
below - one function per section.  Text, timing, colors and crew are in
config.py.
"""
import os
import sys
import math
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy                       # noqa: E402
from mathutils import Vector     # noqa: E402

import config as C               # noqa: E402

# --------------------------------------------------------------------
# CLI arguments (works for both `blender -P x.py -- args` and python3)
# --------------------------------------------------------------------
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]


def _arg(name, default=None):
    if name in argv:
        i = argv.index(name)
        return argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("--") else True
    return default


QUALITY = _arg("--quality", C.QUALITY)
Q = C.QUALITY_PRESETS[QUALITY]

from op_lib import utils as U            # noqa: E402
from op_lib import textures, world, ship as SHIP, characters as CH, props, effects as FX, hud  # noqa: E402
from op_lib.camera import CameraRig      # noqa: E402

R = math.radians
F = C.sec                                # seconds -> frame
DZ = SHIP.DECK_Z

# Where things are (world space, ship at the origin, bow = +Y)
TOKEN_START = Vector((C.TOKEN_START[0], C.TOKEN_START[1], 0.0))  # rises from the sea here
TOKEN_SKY = Vector((0.0, 15.0, 11.0))                            # hovers over the bow (reveal)
TOKEN_GRAB = Vector((0.29, 12.0, 13.0))   # Luffy grabs it here (luffy_grab pose aims at it)
TOKEN_FINALE = Vector((0.3, 6.6, 7.2))    # floats above the crew, in front of the fore sail
LUFFY_HEAD = Vector((C.LUFFY_POS[0], C.LUFFY_POS[1], DZ + 1.85))


# =====================================================================
# SCENE SETUP
# =====================================================================
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.name = "OnePieceFortnite"
    sc.render.fps = C.FPS
    sc.frame_start = C.FRAME_START
    sc.frame_end = C.FRAME_END
    return sc


def setup_render(sc):
    r = sc.render
    r.engine = "CYCLES"
    r.resolution_x = C.WIDTH
    r.resolution_y = C.HEIGHT
    r.resolution_percentage = Q["scale"]
    r.use_motion_blur = Q["motion_blur"]
    try:
        r.motion_blur_position = "START"     # keeps hard cuts clean
        r.motion_blur_shutter = 0.4
    except Exception:
        pass
    cy = sc.cycles
    cy.device = "CPU"
    cy.samples = Q["samples"]
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.05
    cy.use_denoising = True
    try:
        cy.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    cy.max_bounces = 3
    cy.diffuse_bounces = 1
    cy.glossy_bounces = 1
    cy.transmission_bounces = 2
    cy.transparent_max_bounces = 24
    cy.caustics_reflective = False
    cy.caustics_refractive = False
    cy.blur_glossy = 1.0
    cy.sample_clamp_indirect = 8.0
    r.use_persistent_data = False
    r.film_transparent = False
    # color management: AgX, punchy contrast
    vs = sc.view_settings
    try:
        vs.view_transform = "AgX"
        for look in ("AgX - Punchy", "Punchy"):
            try:
                vs.look = look
                break
            except Exception:
                pass
    except Exception:
        pass
    vs.exposure = 0.0
    # output
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGB"
    r.image_settings.compression = 15
    r.filepath = os.path.join(C.FRAMES_DIR, "f_####")
    r.use_overwrite = False                  # resumable rendering
    r.use_placeholder = True                 # several processes can share
    setup_compositor(sc)


def setup_compositor(sc):
    """Bloom/glare for the glowing look (Blender 5 node-group compositor,
    with a fallback for 4.x)."""
    try:
        if hasattr(sc, "compositing_node_group"):
            tree = bpy.data.node_groups.new("Comp", "CompositorNodeTree")
            sc.compositing_node_group = tree
            rl = tree.nodes.new("CompositorNodeRLayers")
            out = tree.nodes.new("NodeGroupOutput")
            tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        else:
            sc.use_nodes = True
            tree = sc.node_tree
            tree.nodes.clear()
            rl = tree.nodes.new("CompositorNodeRLayers")
            out = tree.nodes.new("CompositorNodeComposite")
        glare = tree.nodes.new("CompositorNodeGlare")
        _set_glare(glare)
        tree.links.new(rl.outputs["Image"], glare.inputs["Image"])
        tree.links.new(glare.outputs["Image"], out.inputs[0])
    except Exception as e:                    # never block a render for bloom
        print("WARN compositor setup failed:", e)


def _set_glare(g):
    def setin(name, val):
        if name in g.inputs:
            try:
                g.inputs[name].default_value = val
                return True
            except Exception:
                return False
        return False

    for t in ("Bloom", "BLOOM", "Fog Glow", "FOG_GLOW"):
        if setin("Type", t):
            break
    else:
        try:
            g.glare_type = "BLOOM"
        except Exception:
            g.glare_type = "FOG_GLOW"
    setin("Quality", "Medium") or setin("Quality", "MEDIUM")
    setin("Threshold", 2.5)        # only bright FX / highlights bloom
    setin("Strength", 0.35)
    setin("Size", 0.4)
    setin("Saturation", 1.1)
    for attr, val in (("threshold", 0.9), ("size", 7), ("mix", -0.5), ("quality", "MEDIUM")):
        try:
            setattr(g, attr, val)
        except Exception:
            pass


# =====================================================================
# BUILD
# =====================================================================
def build():
    t0 = time.time()
    sc = reset_scene()
    setup_render(sc)
    tex = textures.make_all()
    end = C.FRAME_END
    E = C.EVENTS
    lightning = [F(t) for t in E["lightning"]]
    day_frame = F(E["dawn_flash"])            # sky switches inside the flash

    U.set_active_collection(U.collection("World"))
    world.build_world(day_frame, 5, lightning)
    world.build_ocean(end, calm_frame=day_frame + 3)
    world.build_lights(day_frame, 5, lightning)

    U.set_active_collection(U.collection("Ship"))
    ship = SHIP.build_ship(tex, end)

    U.set_active_collection(U.collection("Crew"))
    luffy = CH.build_luffy(ship, (C.LUFFY_POS[0], C.LUFFY_POS[1], DZ))
    crew = []
    for spec in C.CREW:
        ch = CH.BUILDERS[spec["builder"]](ship, (spec["pos"][0], spec["pos"][1], DZ))
        ch.spec = spec
        crew.append(ch)

    U.set_active_collection(U.collection("Props"))
    token, token_halo, token_light = props.build_token(tex, TOKEN_START)
    temps = props.build_rain_templates(tex)

    U.set_active_collection(U.collection("Camera"))
    rig = CameraRig()
    flash_w = hud.overlay("FlashWhite", rig.cam, (1.0, 0.95, 0.85), additive=True)
    fade_b = hud.overlay("FadeBlack", rig.cam, (0, 0, 0), additive=False, dist=hud.HUD_DIST * 0.45)

    U.set_active_collection(U.collection("FX"))
    ctx = dict(sc=sc, ship=ship, luffy=luffy, crew=crew, token=token, token_halo=token_halo,
               token_light=token_light, temps=temps, rig=rig, flash=flash_w, fade=fade_b, tex=tex)

    direct_storm(**ctx)
    direct_reveal(**ctx)
    direct_climax(**ctx)
    direct_finale(**ctx)

    # templates live far below the ocean and never render
    for k in ("vbuck", "token", "glider"):
        for o in [temps[k]] + list(temps[k].children):
            o.hide_render = True
    sc.frame_set(1)
    print(f"[build] scene built in {time.time() - t0:.1f}s  "
          f"({len(bpy.data.objects)} objects, frames {sc.frame_start}-{sc.frame_end})")
    return ctx


# =====================================================================
# STORYBOARD
# =====================================================================
def hide_until(ch, f, pop=True, dur=8):
    """Characters stay at ~zero scale (invisible) until frame f."""
    U.key_scale(ch.root, 1, 0.001, "CONSTANT")
    if pop:
        U.key_scale(ch.root, f, 0.001, "BACK")
        U.key_scale(ch.root, f + dur, 1.0, "BEZIER")
    else:
        U.key_scale(ch.root, f, 1.0, "CONSTANT")


def hip_base(ch):
    return ch.dims["thigh"] + ch.dims["shin"] + ch.dims["foot"][2]


def jumps(ch, f0, f1, height=0.35, period=16, phase=0):
    """Celebration hops: keyframe the hips up and down."""
    hz = ch.p["hips"]
    b = hip_base(ch)
    f = f0 + phase
    U.key_loc(hz, f0, (0, 0, b))
    while f + period < f1:
        U.key_loc(hz, f, (0, 0, b), "BEZIER")
        U.key_loc(hz, f + period // 2, (0, 0, b + height), "BEZIER")
        f += period
    U.key_loc(hz, f, (0, 0, b))


def token_spin(token, f0, f1, turns_per_sec=0.35, tilt=8):
    """Slow majestic spin (+ slight wobble) between f0 and f1."""
    n = max(1, (f1 - f0) // 20)
    for i in range(n + 1):
        f = f0 + (f1 - f0) * i // n
        t = (f - 1) / C.FPS
        U.key_rot(token, f, (R(tilt * math.sin(t * 1.3)), R(tilt * 0.5 * math.cos(t)),
                             2 * math.pi * turns_per_sec * t), "LINEAR")


# ---------------------------------------------------------------- 0-8 s
def direct_storm(rig, token, token_halo, token_light, flash, ship, luffy, crew, **_):
    """Dark stormy ocean at night, rain and lightning.  The Pirate Shop
    Token slowly rises from the depths, glowing and spinning, while the
    camera orbits and rises with it.  Empty opened chests drift in the
    waves (all the chests that were NOT the one).  'THE RAREST TREASURE'."""
    f0 = F(C.SECTIONS["storm"][0])
    f1 = F(C.EVENTS["dawn_flash"])
    T = TOKEN_START
    z_of = {f0: -1.8, F(1.0): -1.5, F(6.4): 2.5, F(7.85): 3.0}
    for f, z in z_of.items():
        U.key_loc(token, f, T + Vector((0, 0, z)), "BEZIER")
    token_spin(token, f0, F(16.0), turns_per_sec=0.3)
    # glow builds up, then flares into the dawn flash
    U.key_alpha(token_halo, f0, 0.05)
    U.key_alpha(token_halo, F(4.0), 0.22)
    U.key_alpha(token_halo, F(7.3), 0.4)
    U.key_alpha(token_halo, f1, 1.0)
    U.key_alpha(token_halo, f1 + 12, 0.35)
    for f, e in ((f0, 10), (F(2.5), 60), (F(6.0), 160), (F(7.4), 300), (f1, 3500), (f1 + 12, 250)):
        token_light.energy = e
        token_light.keyframe_insert("energy", frame=f)

    # golden motes + rays around the rising token
    FX.motes("StormMotes", T + Vector((0, 0, -0.3)), 4.0, 70, f0, f1 + 6, (1.0, 0.75, 0.35),
             rise=4.5, size=0.035, strength=10, swirl=1.4)
    FX.light_rays("TokenRays", T + Vector((0, 0, 2.5)), 20, F(3.0), f1 + 4, (1.0, 0.75, 0.3),
                  length=15, width=0.2, strength=1.4, spin=70)
    FX.shock_ring("TokenSplash", T + Vector((0, 0, 0.2)), F(1.2), (0.6, 0.85, 1.0), r_end=5, dur=26,
                  thick=0.025, strength=3)
    # storm: rain + distant lightning bolts
    FX.rain("Rain", (T.x, T.y - 2, 0), size=(26, 26), top=12.0, f0=f0, f1=f1 + 8, count=380)
    for i, lf in enumerate(C.EVENTS["lightning"]):
        x = (-34, 30, -18)[i % 3]
        FX.lightning(f"SkyBolt{i}", (x, -45 + 12 * i, 0), F(lf), (0.75, 0.85, 1.0), n=1, dur=2,
                     height=55, bevel=0.22, jitter=4.0, spread=3.0, strength=30)
        hud.flash(flash, F(lf), peak=0.12, attack=1, release=5)
    # empty opened chests drifting in the waves (the grind)
    import random
    rnd = random.Random(C.SEED + 11)
    for i in range(7):
        a = rnd.uniform(0, 2 * math.pi)
        r = rnd.uniform(4.5, 11)
        p = T + Vector((math.cos(a) * r, math.sin(a) * r * 0.8 - 3, -0.25))
        ch = props.build_empty_chest(f"EmptyChest{i}", p, rnd.uniform(0, 6.28), rnd.uniform(0.35, 0.55))
        for f in range(f0, f1 + 20, 15):
            t = f / C.FPS
            U.key_loc(ch, f, p + Vector((0, 0, 0.25 * math.sin(t * 1.7 + i) - 0.03 * t)))
            U.key_rot(ch, f, (R(9 * math.sin(t * 1.3 + i)), R(9 * math.cos(t * 1.1 + i)), ch.rotation_euler.z))
        U.key(ch, "hide_render", 1, False, "CONSTANT")
        for c in ch.children_recursive:
            U.key(c, "hide_render", 1, False, "CONSTANT")
            U.key(c, "hide_render", f1 + 2, True, "CONSTANT")

    # camera: slow orbit around the token, rising with it
    n = 12
    for i in range(n + 1):
        t = i / n
        ts = t * t * (3 - 2 * t)
        f = int(f0 + (f1 - f0) * t)
        a = R(-35 + 95 * ts)
        rad = 8.0 - 1.5 * ts
        h = 0.8 + 2.9 * ts
        tz = -0.6 + 3.4 * ts
        rig.key(f, T + Vector((math.sin(a) * rad, math.cos(a) * rad, h)), T + Vector((0, 0, tz)),
                38 if i < n else 44)
    hud.title("TXT_rarest", C.TEXT["rarest"], rig.cam, F(C.TEXT_TIMING["rarest"][0]),
              F(C.TEXT_TIMING["rarest"][1]), y=-0.62, width=0.8, style="gold", anim="rise",
              max_height=0.15)
    # FLASH -> sunrise
    hud.flash(flash, f1, peak=1.0, attack=8, release=16, hold=3)
    hide_until(luffy, f1, pop=False)


# --------------------------------------------------------------- 8-16 s
APPEAR_POSES = {
    "ZORO": ("zoro_cross", "zoro_stance"),
    "NAMI": ("rest", "nami_pose"),
    "SANJI": ("sanji_cool", "sanji_kick"),
    "CHOPPER": ("chopper_jump", "chopper_happy"),
}
FX_STYLE = {"slash": "green", "lightning": "blue", "fire": "red", "sparkle": "pink"}


def direct_reveal(rig, luffy, crew, token, token_light, flash, ship, **_):
    """Sunrise.  The token floats higher; the camera pulls back to reveal
    the Going Merry.  Luffy looks up at it with pure determination, and
    the crew appears behind him one by one.  'ONE DROP CAN CHANGE EVERYTHING'."""
    f0 = F(C.SECTIONS["reveal"][0])
    f1 = F(C.SECTIONS["reveal"][1])
    L = LUFFY_HEAD
    # token drifts up over the bow
    U.key_loc(token, F(11.6), TOKEN_SKY, "BEZIER")
    for i, t in enumerate((12.6, 13.6, 14.6, 15.6)):
        U.key_loc(token, F(t), TOKEN_SKY + Vector((0, 0, 0.25 * (-1) ** i)), "BEZIER")
    # its light now shines down on the crew
    for f, e in ((F(11.6), 250), (F(15.9), 450)):
        token_light.energy = e
        token_light.keyframe_insert("energy", frame=f)

    # 1) pull-back reveal: from the token to a wide shot of ship + token
    rig.cut(f0, (1.2, 27.5, 4.2), TOKEN_START + Vector((0, 0, 3.2)), hud.HUD_LENS)
    rig.key(F(9.6), (6.0, 31.0, 7.0), (0, 14.0, 7.0))
    rig.key(F(11.3), (12.5, 34.0, 9.0), (0, 8.0, 6.5))
    # 2) cut: in front of Luffy (over the figurehead), the crew forms behind him
    s = F(11.4)
    rig.cut(s, (3.5, 15.2, 6.1), (0.2, 4.6, 5.0), hud.HUD_LENS)
    rig.key(f1 - 1, (3.0, 13.3, 5.9), (0.2, 4.6, 5.0), hud.HUD_LENS)

    CH.key_pose(luffy, f0, "luffy_look_up")
    CH.key_pose(luffy, F(12.0), "luffy_look_up")
    CH.key_pose(luffy, F(13.0), dict(CH.POSES["luffy_look_up"], head=(24, 0, 6), spine=(4, 0, 3)))
    CH.key_pose(luffy, f1, "luffy_look_up")
    hat = luffy.p["hat"]
    for i, f in enumerate(range(f0, f1, 12)):
        U.key_rot(hat, f, (R(-8 + 3 * math.sin(i)), R(2 * math.cos(i * 1.3)), 0))

    for i, ch in enumerate(crew):
        spec = ch.spec
        a = F(C.EVENTS["crew_appear"][i])
        x, y = spec["pos"]
        base = Vector((x, y, DZ))
        hide_until(ch, a, pop=True, dur=8)
        pa, pb = APPEAR_POSES.get(spec["name"], ("rest", "crew_power"))
        CH.key_pose(ch, a, pa)
        CH.key_pose(ch, a + 12, pb, "BACK")
        CH.key_pose(ch, f1, pb)
        col = spec["color"]
        mid = base + Vector((0, 0, 1.1 if spec["name"] != "CHOPPER" else 0.5))
        FX.shock_ring(f"Ring_{spec['name']}", base + Vector((0, 0, 0.05)), a, col, r_end=2.6, dur=14,
                      parent=ship)
        FX.burst(f"Burst_{spec['name']}", mid, a, col, count=24, speed=4.5, dur=20, parent=ship)
        FX.light_rays(f"Pillar_{spec['name']}", base, 6, a - 2, a + 24, col, length=6, width=0.18,
                      strength=1.2, spin=0, fan=40, parent=ship)
        FX.point_flash(f"Flash_{spec['name']}", mid + Vector((0, 1.0, 0.5)), a, col, peak=900, dur=12,
                       parent=ship)
        FX.motes(f"Motes_{spec['name']}", base, 1.4, 16, a, f1 + 20, col, rise=2.2, size=0.022,
                 strength=10, parent=ship, swirl=2.5)
        hud.flash(flash, a, peak=0.25, attack=1, release=6)
        fx = spec["fx"]
        if fx == "slash":
            FX.slash_arcs(f"Slash_{spec['name']}", mid + Vector((0, 0.3, 0.2)), a + 10, col, parent=ship)
        elif fx == "lightning":
            FX.lightning(f"Bolt_{spec['name']}", base, a + 2, col, parent=ship, n=5, dur=20)
        elif fx == "fire":
            FX.flames(f"Fire_{spec['name']}", ch.p["knee_R"], a + 6, f1 + 2, col, length=0.55)
        elif fx == "sparkle":
            FX.sparkles(f"Spark_{spec['name']}", mid + Vector((0, 0.2, 0.3)), a, col, parent=ship, count=18)
            jumps(ch, a, a + 34, 0.45, 14)
    rig.shake(F(C.EVENTS["crew_appear"][0]), F(C.EVENTS["crew_appear"][-1]) + 8, amp=0.03, freq=3)
    FX.motes("DawnMotes", (0, 4, DZ), 12, 50, f0, f1, (1.0, 0.8, 0.45), rise=5, size=0.04,
             strength=6, height=4)
    hud.title("TXT_onedrop", C.TEXT["one_drop"], rig.cam, F(C.TEXT_TIMING["one_drop"][0]),
              F(C.TEXT_TIMING["one_drop"][1]), y=0.74, width=0.86, style="gold", anim="slam",
              max_height=0.16)


# -------------------------------------------------------------- 16-26 s
SIGNATURE = {"ZORO": "zoro_stance", "NAMI": "nami_pose", "SANJI": "sanji_kick", "CHOPPER": "chopper_happy"}


def direct_climax(rig, luffy, crew, token, token_halo, token_light, temps, flash, ship, **_):
    """GUM-GUM!  Luffy's arm shoots up and grabs the token -> massive
    golden explosion: V-Bucks, free skins, Going Merry gliders and the
    token multiplying fill the sky.  The crew celebrates; the camera
    circles them.  '14 DAYS FREE' / 'TWO TIMES'."""
    E = C.EVENTS
    f0, f1 = F(C.SECTIONS["climax"][0]), F(C.SECTIONS["climax"][1])
    windup, launch, grab, boom = F(E["windup"]), F(E["launch"]), F(E["grab"]), F(E["explosion"])
    retract = boom + 10
    back = boom + 26
    L = LUFFY_HEAD

    # --- token moves to the grab point, pulses on contact
    U.key_loc(token, f0, TOKEN_SKY, "BEZIER")
    U.key_loc(token, launch, TOKEN_GRAB, "BEZIER")
    U.key_scale(token, grab - 1, 1.0, "BEZIER")
    U.key_scale(token, boom, 1.5, "BACK")
    U.key_scale(token, boom + 10, 1.15, "BEZIER")
    U.key_alpha(token_halo, grab, 0.5)
    U.key_alpha(token_halo, boom, 1.0)
    U.key_alpha(token_halo, boom + 40, 0.5)
    for f, e in ((grab, 600), (boom, 9000), (boom + 30, 1500), (f1, 900)):
        token_light.energy = e
        token_light.keyframe_insert("energy", frame=f)

    # --- Luffy: wind-up -> Gum-Gum grab -> snap back -> celebrate
    CH.key_pose(luffy, f0, "luffy_look_up")
    CH.key_pose(luffy, windup, "luffy_windup")
    CH.key_pose(luffy, launch - 2, "luffy_windup")
    CH.key_pose(luffy, launch + 2, "luffy_grab", "EXPO")
    CH.key_pose(luffy, retract + 2, "luffy_grab")
    CH.key_pose(luffy, back, "cheer_fist", "BACK")
    CH.key_pose(luffy, f1, "cheer_fist")
    shoulder = Vector((luffy.dims["shoulder_w"], C.LUFFY_POS[1],
                       DZ + hip_base(luffy) + 0.04 + luffy.dims["torso_h"] - 0.05))
    reach = ((TOKEN_GRAB - shoulder).length - 0.15) / (luffy.dims["upper"] + luffy.dims["fore"])
    CH.key_stretch(luffy, "R", f0, 1.0)
    CH.key_stretch(luffy, "R", launch, 1.0, "EXPO")
    CH.key_stretch(luffy, "R", grab, reach, "BEZIER")
    CH.key_stretch(luffy, "R", retract, reach, "EXPO")
    CH.key_stretch(luffy, "R", back - 4, 1.0, "ELASTIC")
    CH.key_stretch(luffy, "R", back + 30, 1.0)
    jumps(luffy, back + 6, f1, 0.3, 18, 4)
    FX.shock_ring("GumGumRing1", shoulder + Vector((0, 0.5, 0.9)), launch + 1, (1.0, 0.85, 0.5),
                  r_end=1.5, dur=8, thick=0.05, strength=10, parent=ship, rot=(R(-31), 0, 0))
    FX.shock_ring("GumGumRing2", shoulder + Vector((0, 2.5, 4.2)), launch + 4, (1.0, 0.85, 0.5),
                  r_end=2.2, dur=8, thick=0.05, strength=10, parent=ship, rot=(R(-31), 0, 0))

    # --- crew: look up in awe, then CELEBRATE
    for i, ch in enumerate(crew):
        name = ch.spec["name"]
        CH.key_pose(ch, f0, "crew_power")
        CH.key_pose(ch, launch, "crew_power")
        CH.key_pose(ch, grab, "crew_look_up")
        CH.key_pose(ch, boom + 12, "crew_look_up")
        CH.key_pose(ch, boom + 24, "cheer", "BACK")
        CH.key_pose(ch, F(21.5), "cheer")
        CH.key_pose(ch, F(22.2), SIGNATURE.get(name, "cheer"), "BACK")
        CH.key_pose(ch, F(24.0), SIGNATURE.get(name, "cheer"))
        CH.key_pose(ch, F(24.6), "cheer", "BACK")
        CH.key_pose(ch, f1, "cheer")
        jumps(ch, boom + 24, F(21.4), 0.35 if name != "CHOPPER" else 0.5, 16, 3 * i)
        jumps(ch, F(24.6), f1, 0.3, 16, 2 * i)

    # --- THE EXPLOSION
    P = TOKEN_GRAB
    FX.shock_ring("BoomRing", P, boom, (1.0, 0.8, 0.3), r_end=24, dur=18, thick=0.12, strength=14,
                  rot=(R(90), 0, 0))
    FX.shock_ring("BoomRing2", P, boom + 4, (1.0, 0.95, 0.7), r_end=15, dur=16, thick=0.06, strength=10,
                  rot=(R(70), 0, R(30)))
    FX.light_rays("BoomRays", P, 22, boom - 2, f1, (1.0, 0.78, 0.3), length=32, width=0.6,
                  strength=2.5, spin=90)
    FX.burst("BoomSparks", P, boom, (1.0, 0.85, 0.4), count=80, speed=14, dur=34, gravity=-6, size=0.035)
    FX.point_flash("BoomLight", P + Vector((0, 2, -2)), boom, (1.0, 0.8, 0.45), peak=12000, dur=24)
    FX.treasure_rain(temps, P, boom, f1 + 60, n_vbucks=38, n_tokens=24, n_symbols=8,
                     n_cards=14, n_gliders=7, spread=10.0, up=8.0, gravity=-5.0)
    FX.treasure_rain(temps, P + Vector((0, 0, 4)), F(21.0), f1 + 90, n_vbucks=20, n_tokens=8,
                     n_symbols=4, n_cards=8, n_gliders=4, spread=7.0, up=3.0, gravity=-3.0, seed_shift=33)
    hud.flash(flash, boom, peak=0.6, attack=2, release=10)
    FX.motes("UnityMotes", (0, 4.2, DZ), 5.5, 80, back, F(36), (1.0, 0.8, 0.4), rise=5, size=0.035,
             strength=9, swirl=3.0, parent=ship)

    # --- camera
    #  a) low front-right on Luffy (clear of the figurehead), punch zoom on the wind-up
    rig.cut(f0, (4.6, 11.4, 4.1), L + Vector((0, 0, -0.2)), 28)
    rig.key(windup, (3.9, 10.4, 4.3), L, 34)
    rig.key(launch - 1, (3.6, 9.9, 4.3), L, 46)
    #  b) whip up with the stretching arm to the token
    rig.key(launch + 4, (3.4, 10.2, 3.9), L + Vector((0, 2.5, 4.5)), 26)
    rig.key(grab, (3.3, 10.5, 3.8), P + Vector((0, 0, -1.0)), 24)
    rig.key(boom + 10, (3.4, 10.9, 3.7), P + Vector((0, 0, 0.5)), 22)
    rig.shake(boom, boom + 22, amp=0.12)
    #  c) dynamic orbit around the celebrating crew under the treasure rain
    rig.cut(back + 4, (8.5, 12.5, 4.6), (0, 4.6, DZ + 2.6), hud.HUD_LENS)
    rig.orbit(back + 10, f1 - 1, (0, 4.4, DZ + 1.6), 10.0, 40, -100, 3.0, 1.4, step=8,
              lens=hud.HUD_LENS, target_offset=(0, 0, 1.3))

    tt = C.TEXT_TIMING
    hud.title("TXT_days", C.TEXT["days_free"], rig.cam, F(tt["days_free"][0]), F(tt["days_free"][1]),
              y=0.72, width=0.7, style="gold", anim="slam", max_height=0.2)
    hud.flash(flash, F(tt["days_free"][0]), peak=0.3, attack=1, release=6)
    hud.title("TXT_two", C.TEXT["two_times"], rig.cam, F(tt["two_times"][0]), F(tt["two_times"][1]),
              y=0.76, width=0.8, style="white", anim="slam", max_height=0.12)
    hud.title("TXT_two_sub", C.TEXT["two_times_sub"], rig.cam, F(tt["two_times"][0]) + 8,
              F(tt["two_times"][1]), y=0.6, width=0.5, style="gold", anim="rise", max_height=0.05,
              italic=False)
    hud.flash(flash, F(tt["two_times"][0]), peak=0.3, attack=1, release=6)


# -------------------------------------------------------------- 26-36 s
def direct_finale(rig, luffy, crew, token, token_halo, token_light, flash, fade, temps, ship, **_):
    """The crew stands together facing the camera, the token floating
    above them.  KEEP OPENING / THE TOKEN IS OUT THERE / CLAIM YOUR CREW,
    then ONE PIECE x FORTNITE - PIRATE SHOP ACCESS."""
    f0, f1 = F(C.SECTIONS["finale"][0]), C.FRAME_END
    logo_in = F(C.TEXT_TIMING["logo"][0])
    # token hovers above the crew
    U.key_loc(token, f0 - 1, TOKEN_GRAB, "CONSTANT")
    U.key_scale(token, f0 - 1, 1.15, "CONSTANT")
    U.key_scale(token, f0, 1.0, "BEZIER")
    for i, f in enumerate(range(f0, f1 + 1, 30)):
        U.key_loc(token, f, TOKEN_FINALE + Vector((0, 0, 0.15 * math.sin(i * 1.4))), "BEZIER")
    token_spin(token, f0, f1, turns_per_sec=0.25, tilt=6)
    U.key_alpha(token_halo, f0, 0.35)
    U.key_alpha(token_halo, logo_in, 0.4)
    U.key_alpha(token_halo, logo_in + 4, 0.9)
    U.key_alpha(token_halo, f1, 0.6)
    for f, e in ((f0, 350), (logo_in, 350), (logo_in + 3, 2500), (logo_in + 20, 600)):
        token_light.energy = e
        token_light.keyframe_insert("energy", frame=f)

    # poses: united power stance -> signature poses on the logo
    for ch in crew:
        CH.key_pose(ch, f0, "crew_power")
        CH.key_pose(ch, logo_in - 2, "crew_power")
        CH.key_pose(ch, logo_in + 6, SIGNATURE.get(ch.spec["name"], "crew_power"), "BACK")
        CH.key_pose(ch, f1, SIGNATURE.get(ch.spec["name"], "crew_power"))
        U.key_loc(ch.p["hips"], f0, (0, 0, hip_base(ch)))
    CH.key_pose(luffy, f0, "luffy_determined")
    CH.key_pose(luffy, logo_in - 4, "luffy_determined")
    CH.key_pose(luffy, logo_in + 4, "cheer_fist", "BACK")
    CH.key_pose(luffy, f1, "cheer_fist")
    U.key_loc(luffy.p["hips"], f0, (0, 0, hip_base(luffy)))
    for ch in crew:
        if ch.spec["name"] == "CHOPPER":
            jumps(ch, logo_in, f1, 0.5, 16)

    # camera: high front-right (over the figurehead), slow emotional push-in
    rig.cut(f0, (3.4, 14.6, 6.4), (0.3, 4.2, 6.2), hud.HUD_LENS)
    rig.key(logo_in - 2, (3.0, 12.8, 6.3), (0.3, 4.2, 6.1), hud.HUD_LENS)
    rig.key(logo_in + 3, (2.8, 12.2, 6.3), (0.3, 4.2, 6.1), hud.HUD_LENS)     # punch on the logo
    rig.key(f1, (2.7, 11.8, 6.2), (0.3, 4.2, 6.1), hud.HUD_LENS)
    rig.shake(logo_in, logo_in + 12, amp=0.05)

    FX.light_rays("FinaleBurst", (0, -3.0, DZ + 3.5), 22, f0 - 4, f1 + 2, (1.0, 0.75, 0.35),
                  length=34, width=1.0, strength=1.0, spin=25, parent=ship)
    FX.light_rays("TokenCrown", TOKEN_FINALE, 12, f0, f1 + 2, (1.0, 0.8, 0.4), length=5, width=0.12,
                  strength=1.5, spin=60)
    FX.gentle_rain(temps, (0, 3.0, DZ + 4.0), f0, f1, count=24, width=13, height=12)

    styles = ["gold", "white", "red"]
    for i, (line, (a, b)) in enumerate(zip(C.TEXT["final_lines"], C.TEXT_TIMING["final_lines"])):
        hud.title(f"TXT_final{i}", line, rig.cam, F(a), F(b), y=0.8, width=0.84,
                  style=styles[i % 3], anim="slam", max_height=0.16)
        hud.flash(flash, F(a), peak=0.3, attack=1, release=6)
    hud.title("TXT_logo_top", C.TEXT["logo_top"], rig.cam, logo_in, f1 + 2, y=0.86, width=0.86,
              style="gold", anim="slam", max_height=0.1, italic=False)
    hud.title("TXT_logo_x", C.TEXT["logo_x"], rig.cam, logo_in + 4, f1 + 2, y=0.74, width=0.07,
              style="white", anim="pop", max_height=0.04, italic=False)
    hud.title("TXT_logo_bottom", C.TEXT["logo_bottom"], rig.cam, logo_in + 7, f1 + 2, y=0.62, width=0.8,
              style="blue", anim="slam", max_height=0.1, italic=True)
    hud.title("TXT_logo_sub", C.TEXT["logo_sub"], rig.cam, logo_in + 14, f1 + 2, y=-0.8, width=0.84,
              style="gold", anim="slam", max_height=0.07, italic=False)
    hud.flash(flash, logo_in, peak=0.45, attack=1, release=10)
    FX.burst("LogoSparks", TOKEN_FINALE, logo_in + 1, (1.0, 0.85, 0.4), count=40, speed=6, dur=26)
    FX.shock_ring("LogoRing", TOKEN_FINALE, logo_in + 1, (1.0, 0.85, 0.4), r_end=7, dur=14, thick=0.05,
                  strength=10, rot=(R(90), 0, 0))
    # last frames: fade to black
    U.key_alpha(fade, f1 - 12, 0.0, "LINEAR")
    U.key_alpha(fade, f1, 1.0, "LINEAR")


# =====================================================================
# RENDER
# =====================================================================
def render(frames=None, stills=None):
    sc = bpy.context.scene
    os.makedirs(C.FRAMES_DIR, exist_ok=True)
    if stills:
        out_dir = os.path.join(C.BUILD_DIR, "stills")
        os.makedirs(out_dir, exist_ok=True)
        sc.render.image_settings.file_format = "JPEG"
        sc.render.image_settings.quality = 92
        for f in stills:
            sc.frame_set(f)
            sc.render.filepath = os.path.join(out_dir, f"still_{f:04d}.jpg")
            t = time.time()
            bpy.ops.render.render(write_still=True)
            print(f"[still] frame {f} -> {sc.render.filepath}  ({time.time() - t:.1f}s)", flush=True)
        return
    if frames:
        sc.frame_start, sc.frame_end = frames
    print(f"[render] frames {sc.frame_start}-{sc.frame_end} quality={QUALITY}", flush=True)
    bpy.ops.render.render(animation=True)


def main():
    os.makedirs(C.BUILD_DIR, exist_ok=True)
    build()
    if not _arg("--no-save"):
        bpy.ops.wm.save_as_mainfile(filepath=C.BLEND_FILE, compress=True)
        print("[build] saved", C.BLEND_FILE)
    stills = _arg("--stills")
    frames = _arg("--frames")
    if stills and stills is not True:
        render(stills=[int(s) for s in stills.split(",")])
    elif _arg("--render"):
        rng = None
        if frames and frames is not True:
            a, b = frames.split("-")
            rng = (int(a), int(b))
        render(frames=rng)


if __name__ == "__main__":
    main()
