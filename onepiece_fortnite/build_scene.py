"""
=====================================================================
  ONE PIECE x FORTNITE - "Treasure Hunters"  |  MAIN BLENDER SCRIPT
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
TOKEN_POS = Vector((0.0, 36.0, 0.0))
LUFFY_HEAD = Vector((C.LUFFY_POS[0], C.LUFFY_POS[1], DZ + 1.85))
CHEST_POS = Vector((0.3, C.LUFFY_POS[1] + 0.2, 24.6))   # above Luffy's right fist


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

    U.set_active_collection(U.collection("World"))
    day_frame = F(5.85)                       # sky switches during the flash
    world.build_world(day_frame, 6)
    ocean = world.build_ocean(end)
    world.build_lights(day_frame, 6)

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
    token, token_halo, token_light = props.build_token(tex, TOKEN_POS)
    chest, lid, chest_light, chest_glow = props.build_chest(CHEST_POS)
    temps = props.build_rain_templates(tex)

    U.set_active_collection(U.collection("Camera"))
    rig = CameraRig()
    flash_w = hud.overlay("FlashWhite", rig.cam, (1.0, 0.95, 0.85), additive=True)
    fade_b = hud.overlay("FadeBlack", rig.cam, (0, 0, 0), additive=False, dist=hud.HUD_DIST * 0.45)

    U.set_active_collection(U.collection("FX"))
    ctx = dict(sc=sc, ship=ship, luffy=luffy, crew=crew, token=token, token_halo=token_halo,
               token_light=token_light, chest=chest, lid=lid, chest_light=chest_light,
               chest_glow=chest_glow, temps=temps, rig=rig, flash=flash_w, fade=fade_b, tex=tex)

    direct_token(**ctx)
    direct_reveal(**ctx)
    direct_crew(**ctx)
    direct_climax(**ctx)
    direct_finale(**ctx)

    # templates live far below the ocean and never render
    for k in ("vbuck", "token"):
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


# ---------------------------------------------------------------- 0-6 s
def direct_token(rig, token, token_halo, token_light, flash, ship, luffy, crew, **_):
    """Dark ocean at night.  The Pirate Shop Token rises from the water,
    spinning and shining.  Ends with a blinding flash -> sunrise."""
    f0, f1 = F(C.SECTIONS["token"][0]), F(C.SECTIONS["token"][1])
    T = TOKEN_POS
    # token rises out of the water, spinning, gently bobbing
    U.key_loc(token, f0, T + Vector((0, 0, -1.6)), "BEZIER")
    U.key_loc(token, F(1.2), T + Vector((0, 0, -1.2)), "BEZIER")
    U.key_loc(token, F(4.2), T + Vector((0, 0, 2.3)), "BEZIER")
    U.key_loc(token, F(5.6), T + Vector((0, 0, 2.6)), "BEZIER")
    U.key_rot(token, f0, (0, 0, 0), "LINEAR")
    U.key_rot(token, F(5.0), (R(8), 0, R(2.6 * 360)), "EXPO")       # slows into a face-on pose
    U.key_rot(token, F(5.7), (0, 0, R(3 * 360)), "BEZIER")
    # glow ramps up
    U.key_alpha(token_halo, f0, 0.08)
    U.key_alpha(token_halo, F(3.5), 0.25)
    U.key_alpha(token_halo, F(5.3), 0.4)
    U.key_alpha(token_halo, F(5.75), 1.0)
    for f, e in ((f0, 15), (F(2), 60), (F(4.5), 150), (F(5.3), 250), (F(5.75), 3000), (F(6.1), 0)):
        token_light.energy = e
        token_light.keyframe_insert("energy", frame=f)
    # token vanishes inside the flash
    U.key_scale(token, F(5.85), 1.0, "BEZIER")
    U.key_scale(token, F(6.0), 0.001, "CONSTANT")
    U.key_alpha(token_halo, F(5.85), 1.0)
    U.key_alpha(token_halo, F(6.0), 0.0, "CONSTANT")
    U.key(token, "hide_render", F(6.0), True, "CONSTANT")
    for c in token.children:
        U.key(c, "hide_render", 1, False, "CONSTANT")
        U.key(c, "hide_render", F(6.0), True, "CONSTANT")

    # mystical energy motes + light rays around the token
    FX.motes("NightMotes", T + Vector((0, 0, -0.3)), 4.5, 70, f0, F(6.0), (1.0, 0.75, 0.35),
             rise=4.0, size=0.035, strength=10, swirl=1.2)
    FX.motes("NightMotesBlue", T + Vector((0, 0, -0.3)), 7.0, 40, f0, F(6.0), (0.3, 0.6, 1.0),
             rise=3.0, size=0.03, strength=8)
    FX.light_rays("TokenRays", T + Vector((0, 0, 2.3)), 14, F(2.4), F(6.0), (1.0, 0.75, 0.3),
                  length=16, width=0.22, strength=1.6, spin=70)
    FX.shock_ring("TokenSplash", T + Vector((0, 0, 0.15)), F(1.6), (0.6, 0.85, 1.0), r_end=5, dur=24,
                  thick=0.025, strength=3)

    # camera: low over the water, slow dolly-in + rise with the token
    rig.key(f0, (2.6, 47.0, 0.7), T + Vector((0, 0, 0.4)), 38)
    rig.key(F(3.0), (1.8, 44.0, 1.1), T + Vector((0, 0, 1.4)), 38)
    rig.key(F(5.3), (0.9, 41.2, 2.0), T + Vector((0, 0, 2.5)), 42)
    rig.key(F(5.95), (0.6, 40.2, 2.3), T + Vector((0, 0, 2.6)), 50)    # punch-in before the flash

    # FLASH -> sunrise
    hud.flash(flash, F(5.85), peak=1.0, attack=8, release=16, hold=3)

    # crew + Luffy are hidden at night
    hide_until(luffy, F(6.0), pop=False)
    for ch in crew:
        pass  # handled in direct_crew


# --------------------------------------------------------------- 6-14 s
def direct_reveal(rig, luffy, ship, **_):
    """Sunrise.  Camera rises up and reveals the ship with Luffy at the
    bow.  'THE CREW IS ASSEMBLING'."""
    f0, f1 = F(C.SECTIONS["reveal"][0]), F(C.SECTIONS["reveal"][1])
    L = LUFFY_HEAD
    # crane-up reveal: from water level near the token to a high wide shot
    rig.cut(f0, (1.5, 40.0, 1.4), (0, 22, 3.5), hud.HUD_LENS)
    rig.key(F(8.6), (13.0, 33.0, 13.0), (0, 2.0, 6.0))
    # swoop down toward the bow
    rig.key(F(10.8), (7.0, 20.0, 6.0), (0, 5.0, 5.2))
    rig.key(F(12.9), (2.0, 10.2, 4.8), L + Vector((0, 0, 0.4)))
    rig.key(F(13.98), (1.6, 9.5, 4.7), L + Vector((0, 0, 0.45)))
    # Luffy: determined stance, head turns toward the camera at the end
    CH.key_pose(luffy, f0, "luffy_determined")
    CH.key_pose(luffy, F(11.0), "luffy_determined")
    p = dict(CH.POSES["luffy_determined"], head=(8, 0, 14))
    CH.key_pose(luffy, F(12.6), p)
    # hat wind wobble
    hat = luffy.p["hat"]
    for i, f in enumerate(range(f0, f1, 12)):
        U.key_rot(hat, f, (R(-8 + 3 * math.sin(i)), R(2 * math.cos(i * 1.3)), 0))
    # sunrise sparkles drifting around the ship
    FX.motes("DawnMotes", (0, 4, DZ), 12, 60, f0, f1, (1.0, 0.8, 0.45), rise=5, size=0.04,
             strength=6, height=4)
    hud.title("TXT_assembling", C.TEXT["assembling"], rig.cam, F(C.TEXT_TIMING["assembling"][0]),
              F(C.TEXT_TIMING["assembling"][1]), y=0.66, width=0.84, style="gold", anim="slam")


# -------------------------------------------------------------- 14-22 s
CREW_SHOTS = {
    # name: (camera offset from the character, look-at height, lens)
    "ZORO": ((-1.6, 4.4, 1.55), 1.25, 30),
    "NAMI": ((1.7, 4.3, 1.45), 1.2, 30),
    "SANJI": ((-1.9, 4.6, 1.5), 1.2, 30),
    "CHOPPER": ((0.9, 2.8, 1.3), 0.6, 30),
}
APPEAR_POSES = {
    "ZORO": ("zoro_cross", "zoro_stance"),
    "NAMI": ("rest", "nami_pose"),
    "SANJI": ("sanji_cool", "sanji_kick"),
    "CHOPPER": ("chopper_jump", "chopper_happy"),
}


def direct_crew(rig, crew, flash, ship, luffy, **_):
    """The Straw Hats appear one by one with their signature effects."""
    f0, f1 = F(C.SECTIONS["crew"][0]), F(C.SECTIONS["crew"][1])
    shot_len = (f1 - f0) // len(crew)
    CH.key_pose(luffy, f0, "luffy_determined")
    for i, ch in enumerate(crew):
        spec = ch.spec
        s = f0 + i * shot_len
        a = s + 8                                       # appear frame
        x, y = spec["pos"]
        base = Vector((x, y, DZ))
        off, look_h, lens = CREW_SHOTS.get(spec["name"], ((1.5, 4.4, 1.5), 1.2, 30))
        off = Vector(off)
        tgt = base + Vector((0, 0, look_h))
        # camera: cut in, slow push + slight arc, small punch at appear
        rig.cut(s, base + off * 1.18 + Vector((0, 0, 0.2)), tgt + Vector((0, 0, 0.1)), lens)
        rig.key(a + 4, base + off * 1.0, tgt, lens)
        side = Vector((off.y, -off.x, 0)).normalized() * 0.6
        rig.key(s + shot_len - 1, base + off * 0.9 + side, tgt + Vector((0, 0, 0.05)), lens)
        rig.shake(a, a + 10, amp=0.05)

        # character pops in with overshoot, then hits the signature pose
        hide_until(ch, a, pop=True, dur=8)
        pose_a, pose_b = APPEAR_POSES.get(spec["name"], ("rest", "crew_power"))
        CH.key_pose(ch, a, pose_a)
        CH.key_pose(ch, a + 12, pose_b, "BACK")
        CH.key_pose(ch, s + shot_len + 10, pose_b)

        # shared appearance FX (in ship space so they bob with the deck)
        col = spec["color"]
        chest = base + Vector((0, 0, 1.1 if spec["name"] != "CHOPPER" else 0.5))
        FX.shock_ring(f"Ring_{spec['name']}", base + Vector((0, 0, 0.05)), a, col, r_end=3.2, dur=14,
                      parent=ship)
        FX.burst(f"Burst_{spec['name']}", chest, a, col, count=28, speed=5, dur=20, parent=ship)
        FX.light_rays(f"Pillar_{spec['name']}", base, 6, a - 2, a + 26, col, length=7, width=0.2,
                      strength=1.2, spin=0, fan=40, parent=ship)
        FX.point_flash(f"Flash_{spec['name']}", chest + Vector((0, 1.0, 0.5)), a, col, peak=1500,
                       dur=14, parent=ship)
        FX.motes(f"Motes_{spec['name']}", base, 1.6, 22, a, s + shot_len + 30, col, rise=2.5,
                 size=0.025, strength=10, parent=ship, swirl=2.5)
        hud.flash(flash, a, peak=0.55, attack=2, release=8)

        fx = spec["fx"]
        if fx == "slash":
            FX.slash_arcs(f"Slash_{spec['name']}", chest + Vector((0, 0.3, 0.2)), a + 10, col, parent=ship)
            FX.slash_arcs(f"Slash2_{spec['name']}", chest + Vector((0, 0.3, 0.3)), a + 30, col, parent=ship)
        elif fx == "lightning":
            FX.lightning(f"Bolt_{spec['name']}", base, a + 2, col, parent=ship, n=6, dur=36)
        elif fx == "fire":
            FX.flames(f"Fire_{spec['name']}", ch.p["knee_R"], a + 6, s + shot_len + 2, col, length=0.55)
            FX.flames(f"Fire2_{spec['name']}", ch.p["hip_R"], a + 8, s + shot_len + 2, col, length=0.4,
                      count=6)
        elif fx == "sparkle":
            FX.sparkles(f"Spark_{spec['name']}", chest + Vector((0, 0.2, 0.3)), a, col, parent=ship)
            # Chopper hops!
            hz = ch.p["hips"]
            hip0 = ch.dims["thigh"] + ch.dims["shin"] + ch.dims["foot"][2]
            for k, (df, dz) in enumerate(((0, 0), (6, 0.55), (14, 0), (22, 0.3), (28, 0))):
                U.key_loc(hz, a + df, (0, 0, hip0 + dz), "BEZIER")

        if C.SHOW_CREW_NAMES:
            hud.title(f"TXT_name_{spec['name']}", spec["name"], rig.cam, a + 3, s + shot_len - 2,
                      y=-0.70, width=0.55, style={"slash": "green", "lightning": "blue", "fire": "red",
                                                   "sparkle": "pink"}.get(fx, "gold"),
                      anim="slam", max_height=0.08)

    hud.title("TXT_onebyone", C.TEXT["one_by_one"], rig.cam, F(C.TEXT_TIMING["one_by_one"][0]),
              F(C.TEXT_TIMING["one_by_one"][1]), y=0.74, width=0.8, style="gold", anim="slam",
              max_height=0.1)


# -------------------------------------------------------------- 22-30 s
def direct_climax(rig, luffy, crew, chest, lid, chest_light, chest_glow, temps, flash, ship, **_):
    """GUM-GUM! Luffy's arm stretches into the sky, punches the giant
    treasure chest, which explodes into a rain of V-Bucks, tokens and
    glowing One Piece symbols.  Camera circles the united crew."""
    f0, f1 = F(C.SECTIONS["climax"][0]), F(C.SECTIONS["climax"][1])
    windup = F(22.9)
    launch = F(23.6)
    impact = F(24.15)
    retract = F(24.5)
    back = F(25.1)
    L = LUFFY_HEAD

    # --- crew poses
    for ch in crew:
        CH.key_pose(ch, f0, "crew_power")
        CH.key_pose(ch, launch, "crew_power")
        CH.key_pose(ch, impact - 3, "crew_look_up")
        CH.key_pose(ch, impact + 25, "crew_look_up")
    sig = {"ZORO": "zoro_stance", "NAMI": "nami_pose", "SANJI": "sanji_cool", "CHOPPER": "chopper_happy"}
    for ch in crew:
        CH.key_pose(ch, impact + 40, sig.get(ch.spec["name"], "crew_power"), "BACK")
        CH.key_pose(ch, f1, sig.get(ch.spec["name"], "crew_power"))

    # --- Luffy: wind-up -> punch up (stretch) -> snap back
    CH.key_pose(luffy, f0, "luffy_determined")
    CH.key_pose(luffy, windup, "luffy_windup")
    CH.key_pose(luffy, launch - 2, "luffy_windup")
    CH.key_pose(luffy, launch + 3, "luffy_punch_up", "EXPO")
    CH.key_pose(luffy, retract + 2, "luffy_punch_up")
    CH.key_pose(luffy, back + 6, "luffy_determined", "BACK")
    CH.key_pose(luffy, f1, "luffy_determined")
    shoulder_z = DZ + (luffy.dims["thigh"] + luffy.dims["shin"] + luffy.dims["foot"][2]) + 0.04 \
        + luffy.dims["torso_h"] - 0.05
    reach = (CHEST_POS.z - 0.2 - shoulder_z) / (luffy.dims["upper"] + luffy.dims["fore"])
    CH.key_stretch(luffy, "R", f0, 1.0)
    CH.key_stretch(luffy, "R", launch, 1.0, "EXPO")
    CH.key_stretch(luffy, "R", impact, reach, "BEZIER")
    CH.key_stretch(luffy, "R", retract, reach * 1.03, "EXPO")
    CH.key_stretch(luffy, "R", back, 1.0, "ELASTIC")
    CH.key_stretch(luffy, "R", back + 30, 1.0)
    # rubber "wobble" rings along the arm at launch
    FX.shock_ring("GumGumRing1", (0.3, C.LUFFY_POS[1], shoulder_z + 1.0), launch + 1, (1.0, 0.85, 0.5),
                  r_end=1.6, dur=8, thick=0.06, strength=10, parent=ship)
    FX.shock_ring("GumGumRing2", (0.3, C.LUFFY_POS[1], shoulder_z + 5.0), launch + 4, (1.0, 0.85, 0.5),
                  r_end=2.2, dur=8, thick=0.06, strength=10, parent=ship)
    FX.motes("GumGumTrail", (0.3, C.LUFFY_POS[1], shoulder_z + 2), 0.6, 40, launch, impact + 10,
             (1.0, 0.9, 0.6), rise=18, size=0.03, strength=12, parent=ship, height=4)

    # --- the chest: appears glowing in the sky, then EXPLODES
    U.key_scale(chest, 1, 0.001, "CONSTANT")
    U.key_scale(chest, f0, 0.001, "BACK")
    U.key_scale(chest, f0 + 12, 1.0, "BEZIER")
    U.key_rot(chest, f0, (0, 0, R(-25)), "BEZIER")
    U.key_rot(chest, impact, (0, 0, R(10)), "BEZIER")
    U.key_alpha(chest_glow, f0, 0.1)
    U.key_alpha(chest_glow, impact - 2, 0.25)
    U.key_alpha(chest_glow, impact + 2, 0.7)
    U.key_alpha(chest_glow, impact + 40, 0.0)
    for f, e in ((f0, 0), (f0 + 10, 300), (impact, 600), (impact + 2, 6000), (impact + 30, 1500), (f1, 600)):
        chest_light.energy = e
        chest_light.keyframe_insert("energy", frame=f)
    U.key_rot(lid, impact, (0, 0, 0), "EXPO")
    U.key_rot(lid, impact + 10, (R(-150), R(20), 0), "BEZIER")
    U.key_loc(lid, impact, lid.location.copy(), "EXPO")
    U.key_loc(lid, impact + 30, lid.location + Vector((1.5, -2.5, 5.0)), "BEZIER")
    # chest punch-bump + slow fall afterwards
    U.key_loc(chest, impact, CHEST_POS, "EXPO")
    U.key_loc(chest, impact + 6, CHEST_POS + Vector((0, 0, 1.2)), "BEZIER")
    U.key_loc(chest, f1, CHEST_POS + Vector((0, 0, 2.5)), "BEZIER")

    top = CHEST_POS + Vector((0, 0, 1.8))
    FX.shock_ring("ChestRing", top, impact, (1.0, 0.8, 0.3), r_end=22, dur=18, thick=0.12, strength=14,
                  rot=(R(90), 0, 0))
    FX.shock_ring("ChestRing2", top, impact + 4, (1.0, 0.95, 0.7), r_end=14, dur=16, thick=0.06, strength=10,
                  rot=(R(70), 0, R(30)))
    FX.light_rays("ChestRays", top, 18, impact - 2, f1, (1.0, 0.78, 0.3), length=30, width=0.6,
                  strength=2.5, spin=90)
    FX.burst("ChestSparks", top, impact, (1.0, 0.85, 0.4), count=70, speed=14, dur=34, gravity=-6, size=0.035)
    FX.treasure_rain(temps, top, impact, f1 + 60, n_vbucks=44, n_tokens=14, n_symbols=18,
                     spread=8.0, up=9.0, gravity=-5.5)
    hud.flash(flash, impact, peak=0.5, attack=2, release=8)

    # energy swirling around the united crew
    FX.motes("UnityMotes", (0, 4.2, DZ), 5.5, 90, back, F(37), (1.0, 0.8, 0.4), rise=5, size=0.035,
             strength=9, swirl=3.0, parent=ship)

    # --- camera
    #  a) low wide hero shot of the crew from front-right (clear of the
    #     figurehead), slow push toward Luffy
    rig.cut(f0, (7.5, 14.5, 4.0), (0, 4.6, 4.1), 26)
    rig.key(windup, (4.2, 10.4, 4.3), L + Vector((0, 0, -0.1)), 30)
    #  b) punch zoom on the wind-up
    rig.key(launch - 2, (3.6, 9.8, 4.3), L + Vector((0, 0, 0.0)), 48)
    #  c) whip up with the fist into the sky (vertical frame!)
    rig.key(launch + 6, (3.4, 10.4, 3.9), L + Vector((0, 0, 6.0)), 24)
    rig.key(impact - 2, (3.2, 10.8, 3.8), CHEST_POS + Vector((0, 0, -3.0)), 20)
    rig.key(impact + 8, (3.3, 11.0, 3.7), CHEST_POS + Vector((0, 0, -1.0)), 20)
    rig.shake(impact, impact + 22, amp=0.12)
    #  d) orbit the crew while the treasure rains down
    rig.key(back + 8, (7.5, 14.5, 5.5), (0, 4.4, 4.6), 26)
    rig.orbit(back + 14, f1 - 1, (0, 4.4, DZ + 1.6), 10.5, 32, -95, 3.4, 2.0, step=8, lens=26,
              target_offset=(0, 0, 0.5))


# -------------------------------------------------------------- 30-37 s
def direct_finale(rig, luffy, crew, flash, fade, temps, ship, **_):
    """The crew faces the camera.  Big texts one after another, then the
    ONE PIECE x FORTNITE logo with Luffy's fist raised."""
    f0, f1 = F(C.SECTIONS["finale"][0]), C.FRAME_END
    logo_in = F(C.TEXT_TIMING["logo"][0])
    # poses
    for ch in crew:
        CH.key_pose(ch, f0, "crew_power")
        CH.key_pose(ch, logo_in - 2, "crew_power")
    final = {"ZORO": "zoro_stance", "NAMI": "nami_pose", "SANJI": "sanji_kick", "CHOPPER": "chopper_jump"}
    for ch in crew:
        CH.key_pose(ch, logo_in + 6, final.get(ch.spec["name"], "crew_power"), "BACK")
        CH.key_pose(ch, f1, final.get(ch.spec["name"], "crew_power"))
    CH.key_pose(luffy, f0, "luffy_determined")
    CH.key_pose(luffy, logo_in - 4, "luffy_determined")
    CH.key_pose(luffy, logo_in + 4, "luffy_victory", "BACK")
    CH.key_pose(luffy, f1, "luffy_victory")
    # Chopper's jump in the final pose
    for ch in crew:
        if ch.spec["name"] == "CHOPPER":
            hz = ch.p["hips"]
            hip0 = ch.dims["thigh"] + ch.dims["shin"] + ch.dims["foot"][2]
            U.key_loc(hz, logo_in + 2, (0, 0, hip0 + 0.6), "BEZIER")
            U.key_loc(hz, logo_in + 30, (0, 0, hip0 + 0.45), "BEZIER")

    # camera: front, slightly low, crew in the lower half; slow push-in
    # (camera high and slightly right so it looks OVER the sheep figurehead)
    rig.cut(f0, (3.3, 14.2, 6.7), (0.3, 4.2, 6.1), hud.HUD_LENS)
    rig.key(logo_in - 2, (3.0, 12.6, 6.4), (0.3, 4.2, 6.0), hud.HUD_LENS)
    rig.key(logo_in + 3, (2.8, 12.0, 6.3), (0.3, 4.2, 6.0), hud.HUD_LENS)     # punch on logo
    rig.key(f1, (2.7, 11.6, 6.2), (0.3, 4.2, 6.0), hud.HUD_LENS)
    rig.shake(logo_in, logo_in + 12, amp=0.06)

    # sunburst behind the crew + gentle coin rain
    FX.light_rays("FinaleBurst", (0, -3.0, DZ + 3.5), 22, f0 - 4, f1 + 2, (1.0, 0.75, 0.35),
                  length=34, width=1.0, strength=1.0, spin=25, parent=ship)
    FX.gentle_rain(temps, (0, 3.0, DZ + 4.0), f0, f1, count=26, width=13, height=12)

    # titles one after another (stacked), then the logo
    ys = [0.82, 0.55, 0.28]
    styles = ["gold", "white", "red"]
    for i, (line, (a, b)) in enumerate(zip(C.TEXT["final_lines"], C.TEXT_TIMING["final_lines"])):
        hud.title(f"TXT_final{i}", line, rig.cam, F(a), F(b), y=ys[i], width=0.82,
                  style=styles[i % 3], anim="slam", max_height=0.13)
        hud.flash(flash, F(a), peak=0.35, attack=1, release=6)
    hud.title("TXT_logo_top", C.TEXT["logo_top"], rig.cam, logo_in, f1 + 2, y=0.70, width=0.9,
              style="gold", anim="slam", max_height=0.12, italic=False)
    hud.title("TXT_logo_x", C.TEXT["logo_x"], rig.cam, logo_in + 4, f1 + 2, y=0.53, width=0.08,
              style="white", anim="pop", max_height=0.05, italic=False)
    hud.title("TXT_logo_bottom", C.TEXT["logo_bottom"], rig.cam, logo_in + 7, f1 + 2, y=0.38, width=0.82,
              style="blue", anim="slam", max_height=0.11, italic=True)
    hud.title("TXT_logo_sub", C.TEXT["logo_sub"], rig.cam, logo_in + 14, f1 + 2, y=0.23, width=0.6,
              style="gold", anim="rise", max_height=0.04, italic=False)
    hud.flash(flash, logo_in, peak=0.45, attack=1, release=10)
    FX.burst("LogoSparks", (0, 6.2, DZ + 2.4), logo_in + 2, (1.0, 0.85, 0.4), count=40, speed=7, dur=26,
             parent=ship)
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
