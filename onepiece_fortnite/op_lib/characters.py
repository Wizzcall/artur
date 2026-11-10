"""
Stylized crew characters built from primitives on a simple "puppet rig":

    root (feet) -> hips -> spine -> chest/shoulders -> elbows -> hands
                        -> hip_L/R -> knees -> feet
                   spine -> head (face, hair, hat)

Each joint is an Empty, so poses are just Euler rotations (degrees) on
pivots - see POSES and `key_pose()`.  Character faces +Y, right = +X.

Arm/leg rotation cheat-sheet (arms hang along -Z):
    X+ : swing forward / up in front      (X=180 -> straight up)
    Y- : right arm out to the side        (Y+ for the left arm)
    knee/elbow X : bend
    head / spine X+ : look up / lean back,  X- : look down / lean forward
    head / spine Z  : turn left/right
"""
import math
import random
import bpy
from mathutils import Vector, Euler

import config as C
from .utils import (empty, sphere, cyl, box, torus, obj_from_mesh, mesh_cylinder, mat_basic,
                    mat_emit_fade, key, key_rot, key_scale, key_loc, add_subsurf, no_shadow)

R = math.radians


# ---------------------------------------------------------------------
# Shared materials
# ---------------------------------------------------------------------
def M(name, color, rough=0.5, metal=0.0, **kw):
    return mat_basic(name, color, rough=rough, metal=metal, **kw)


def skin():
    # (no subsurface scattering on purpose: big render-time saving on CPU)
    return M("Skin", C.COLORS["skin"], rough=0.45)


def stripes_mat(name, c1, c2, scale=9.0):
    """Horizontal stripes (Nami's top)."""
    m = M(name, c1, rough=0.6)
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    w = nt.nodes.new("ShaderNodeTexWave")
    w.wave_type = "BANDS"
    w.bands_direction = "Z"
    w.inputs["Scale"].default_value = scale
    w.inputs["Distortion"].default_value = 0.0
    nt.links.new(tc.outputs["Object"], w.inputs["Vector"])
    r = nt.nodes.new("ShaderNodeValToRGB")
    r.color_ramp.interpolation = "CONSTANT"
    r.color_ramp.elements[0].color = (*c1, 1)
    r.color_ramp.elements[1].position = 0.5
    r.color_ramp.elements[1].color = (*c2, 1)
    nt.links.new(w.outputs["Fac"], r.inputs[0])
    nt.links.new(r.outputs["Color"], b.inputs["Base Color"])
    return m


def straw_mat():
    m = M("Straw", C.COLORS["straw_yellow"], rough=0.7)
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    w = nt.nodes.new("ShaderNodeTexWave")
    w.wave_type = "RINGS"
    w.inputs["Scale"].default_value = 30
    w.inputs["Distortion"].default_value = 2
    nt.links.new(tc.outputs["Object"], w.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.25
    nt.links.new(w.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


# ---------------------------------------------------------------------
# The rig
# ---------------------------------------------------------------------
class Char:
    """Container for one character: pivots, sizes and helper meshes."""

    def __init__(self, name):
        self.name = name
        self.root = None
        self.p = {}            # pivots by name
        self.dims = {}
        self.parts = {}        # stretchable meshes (upper arm etc.)
        self.fx_parent = None  # an empty at the chest for effects


DEFAULT_DIMS = dict(
    thigh=0.44, shin=0.42, leg_r=0.085, hip_w=0.11,
    torso_h=0.52, waist_r=0.16, chest_r=0.22, torso_depth=0.72,
    shoulder_w=0.29, upper=0.30, fore=0.28, arm_r=0.065, hand_r=0.075,
    neck=0.08, head_r=0.25, foot=(0.11, 0.24, 0.08),
)


def build_body(name, mats, dims=None, parent=None, loc=(0, 0, 0)):
    """Generic body.  mats: dict with keys
       skin, top, bottom, shoe, (sleeve), (hand)  -> materials."""
    d = dict(DEFAULT_DIMS)
    d.update(dims or {})
    ch = Char(name)
    ch.dims = d
    sk = mats["skin"]
    hip_z = d["thigh"] + d["shin"] + d["foot"][2]

    root = empty(f"{name}", parent, loc, size=0.4)
    ch.root = root
    hips = empty(f"{name}_hips", root, (0, 0, hip_z))
    ch.p["hips"] = hips
    # pelvis
    sphere(f"{name}_pelvis", d["waist_r"] * 1.08, mats["bottom"], hips, (0, 0, 0.02),
           scale=(1.15, d["torso_depth"] * 1.05, 0.75))

    # ---- legs ----------------------------------------------------------
    for side, sx in (("R", 1), ("L", -1)):
        hp = empty(f"{name}_hip_{side}", hips, (sx * d["hip_w"], 0, -0.02))
        hp.rotation_mode = "YXZ"        # spread first (Y), then swing (X)
        ch.p[f"hip_{side}"] = hp
        cyl(f"{name}_thigh_{side}", d["leg_r"] * 1.15, d["thigh"], mats.get("thigh", mats["bottom"]),
            hp, top_origin=True, r2=d["leg_r"] * 1.35, seg=16)
        kn = empty(f"{name}_knee_{side}", hp, (0, 0, -d["thigh"]))
        ch.p[f"knee_{side}"] = kn
        sphere(f"{name}_kneeball_{side}", d["leg_r"] * 1.05, mats.get("shin", sk), kn, seg=16)
        cyl(f"{name}_shin_{side}", d["leg_r"] * 0.8, d["shin"], mats.get("shin", sk), kn,
            top_origin=True, r2=d["leg_r"] * 1.02, seg=16)
        ft = empty(f"{name}_foot_{side}", kn, (0, 0, -d["shin"]))
        ch.p[f"foot_{side}"] = ft
        fx, fy, fz = d["foot"]
        box(f"{name}_shoe_{side}", (fx * 2, fy, fz), mats["shoe"], ft,
            (0, fy * 0.3, -fz / 2), bevel=0.03)

    # ---- torso -----------------------------------------------------------
    spine = empty(f"{name}_spine", hips, (0, 0, 0.04))
    ch.p["spine"] = spine
    tme = mesh_cylinder(f"{name}_torso", d["waist_r"], d["torso_h"], 16, r2=d["chest_r"])
    torso = obj_from_mesh(f"{name}_torso", tme, mats["top"], spine, (0, 0, d["torso_h"] / 2),
                          scale=(1, d["torso_depth"], 1))
    add_subsurf(torso, 2)
    ch.parts["torso"] = torso
    # shoulders cap
    sphere(f"{name}_chestcap", d["chest_r"] * 0.98, mats["top"], spine, (0, 0, d["torso_h"] - 0.03),
           scale=(1.05, d["torso_depth"] * 0.98, 0.42))
    ch.fx_parent = empty(f"{name}_fx", spine, (0, 0, d["torso_h"] * 0.6))

    # ---- arms --------------------------------------------------------------
    sh_z = d["torso_h"] - 0.05
    for side, sx in (("R", 1), ("L", -1)):
        sh = empty(f"{name}_sh_{side}", spine, (sx * d["shoulder_w"], 0, sh_z))
        sh.rotation_mode = "YXZ"        # spread first (Y), then swing (X)
        ch.p[f"sh_{side}"] = sh
        sphere(f"{name}_shball_{side}", d["arm_r"] * 1.35, mats.get("sleeve", mats["top"]), sh, seg=16)
        ua = cyl(f"{name}_upper_{side}", d["arm_r"], d["upper"], mats.get("upper", sk), sh,
                 top_origin=True, r2=d["arm_r"] * 1.1, seg=16)
        ch.parts[f"upper_{side}"] = ua
        el = empty(f"{name}_el_{side}", sh, (0, 0, -d["upper"]))
        ch.p[f"el_{side}"] = el
        sphere(f"{name}_elball_{side}", d["arm_r"] * 0.95, mats.get("upper", sk), el, seg=16)
        fa = cyl(f"{name}_fore_{side}", d["arm_r"] * 0.85, d["fore"], mats.get("fore", sk), el,
                 top_origin=True, r2=d["arm_r"] * 0.95, seg=16)
        ch.parts[f"fore_{side}"] = fa
        hd = empty(f"{name}_hand_{side}", el, (0, 0, -d["fore"]))
        ch.p[f"hand_{side}"] = hd
        fist = sphere(f"{name}_fist_{side}", d["hand_r"], mats.get("hand", sk), hd, (0, 0.0, -d["hand_r"] * 0.7),
                      scale=(0.95, 1.05, 1.1))
        ch.parts[f"fist_{side}"] = fist

    # ---- neck + head -----------------------------------------------------
    sphere(f"{name}_neck", d["arm_r"] * 1.25, sk, spine, (0, 0, d["torso_h"] + 0.02), scale=(1, 1, 1.3))
    head = empty(f"{name}_head", spine, (0, 0, d["torso_h"] + d["neck"]))
    ch.p["head"] = head
    hr = d["head_r"]
    sphere(f"{name}_skull", hr, sk, head, (0, 0, hr * 0.92), scale=(0.93, 0.95, 1.0))
    sphere(f"{name}_jaw", hr * 0.72, sk, head, (0, hr * 0.12, hr * 0.55), scale=(1.0, 1.0, 0.9))
    # ears
    for sx in (-1, 1):
        sphere(f"{name}_ear{sx}", hr * 0.16, sk, head, (sx * hr * 0.9, -0.02, hr * 0.85),
               scale=(0.5, 0.9, 1.2))
    ch.head_center = Vector((0, 0, hr * 0.92))
    ch.height = hip_z + 0.04 + d["torso_h"] + d["neck"] + 2 * hr
    return ch


# ---------------------------------------------------------------------
# Face helpers
# ---------------------------------------------------------------------
def face_point(ch, az, el, out=0.0):
    """Point on the head sphere: az = degrees to the character's right,
    el = degrees up.  Returns (location, rotation) facing outward."""
    hr = ch.dims["head_r"]
    a, e = R(az), R(el)
    dvec = Vector((math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e)))
    loc = ch.head_center + Vector((dvec.x * 0.93, dvec.y * 0.95, dvec.z)) * (hr + out)
    rot = dvec.to_track_quat("Y", "Z").to_euler()
    return loc, rot


def add_eyes(ch, iris=(0.05, 0.03, 0.02), size=1.0, brow_angle=12, brow_mat=None,
             skip_left=False, eye_el=4, squint=1.0):
    head = ch.p["head"]
    hr = ch.dims["head_r"]
    white = M("EyeWhite", (0.95, 0.95, 0.95), rough=0.2)
    iris_m = M(f"Iris_{ch.name}", iris, rough=0.15)
    hl = mat_emit_fade("EyeHighlight", (1, 1, 1), 3.0)
    brow = brow_mat or M("BrowBlack", (0.02, 0.02, 0.02))
    for side, sx in (("R", 1), ("L", -1)):
        if skip_left and side == "L":
            continue
        loc, rot = face_point(ch, sx * 22, eye_el, -0.015)
        ew = sphere(f"{ch.name}_eye_{side}", hr * 0.17 * size, white, head, loc,
                    scale=(1.0, 0.45, 1.25 * squint), rot=rot)
        loc2, rot2 = face_point(ch, sx * 22, eye_el, 0.0)
        sphere(f"{ch.name}_iris_{side}", hr * 0.11 * size, iris_m, head, loc2,
               scale=(1.0, 0.4, 1.25 * squint), rot=rot2)
        loc3, rot3 = face_point(ch, sx * 19, eye_el + 4, 0.012)
        h = sphere(f"{ch.name}_hl_{side}", hr * 0.03 * size, hl, head, loc3, rot=rot3)
        h.color = (1, 1, 1, 1)
        no_shadow(h)
        # eyebrow: tilted down toward the nose = determined look
        loc4, rot4 = face_point(ch, sx * 22, eye_el + 17, 0.0)
        b = box(f"{ch.name}_brow_{side}", (hr * 0.38, hr * 0.06, hr * 0.07), brow, head, loc4)
        b.rotation_euler = (rot4.x, rot4.y, rot4.z)
        b.rotation_mode = "XYZ"
        b.rotation_euler.rotate(Euler((0, -sx * R(brow_angle), 0)))


def add_mouth(ch, kind="grin"):
    head = ch.p["head"]
    hr = ch.dims["head_r"]
    dark = M("MouthDark", (0.25, 0.02, 0.02), rough=0.4)
    teeth = M("Teeth", (0.98, 0.98, 0.95), rough=0.3)
    line = M("MouthLine", (0.12, 0.03, 0.03), rough=0.5)
    if kind == "grin":           # big Luffy smile
        loc, rot = face_point(ch, 0, -32, -0.03)
        sphere(f"{ch.name}_mouth", hr * 0.36, dark, head, loc, scale=(1.0, 0.35, 0.42), rot=rot)
        loc2, rot2 = face_point(ch, 0, -25, -0.02)
        sphere(f"{ch.name}_teeth", hr * 0.33, teeth, head, loc2, scale=(1.0, 0.3, 0.16), rot=rot2)
    elif kind == "smile":
        # half torus rotated so the arc forms a "U" on the face plane
        loc, rot = face_point(ch, 0, -24, -0.005)
        torus(f"{ch.name}_mouth", hr * 0.16, hr * 0.03, line, head, loc,
              rot=(R(-90 + 25), 0, 0), arc=math.pi)
    else:                        # serious line / smirk
        loc, rot = face_point(ch, 0 if kind == "line" else 6, -30, -0.005)
        b = box(f"{ch.name}_mouth", (hr * 0.32, hr * 0.05, hr * 0.045), line, head, loc, rot=rot)
        if kind == "smirk":
            b.rotation_euler.y += R(-10)
    # nose
    loc, rot = face_point(ch, 0, -12, -0.01)
    sphere(f"{ch.name}_nose", hr * 0.07, mats_skin_cache(), head, loc, rot=rot)


def mats_skin_cache():
    return bpy.data.materials.get("Skin") or skin()


def hair_cap(ch, mat, name="hair", scale=(1.04, 1.06, 1.0), z=0.0, front_cut=0.62):
    """Hair 'helmet' = slightly bigger sphere pushed up and back."""
    hr = ch.dims["head_r"]
    return sphere(f"{ch.name}_{name}", hr, mat, ch.p["head"],
                  (0, -hr * 0.2, ch.head_center.z + hr * 0.26 + z), scale=scale)


def spikes(ch, mat, n=9, length=0.16, spread=1.0, z=0.18, rng_seed=1, rows=2, droop=0.0):
    """Spiky hair: cones radiating from the head."""
    rnd = random.Random(rng_seed)
    hr = ch.dims["head_r"]
    out = []
    for row in range(rows):
        for i in range(n):
            az = -150 + 300 * (i + 0.5 * row) / n
            el = 10 + row * 30 + rnd.uniform(-6, 6)
            loc, rot = face_point(ch, az + 180 if False else az, el, -0.04)
            loc = loc + Vector((0, -hr * 0.25, hr * z))
            d = (loc - ch.head_center).normalized()
            d.z -= droop
            q = d.to_track_quat("Z", "Y").to_euler()
            c = cyl(f"{ch.name}_spike{row}_{i}", hr * 0.18, length * rnd.uniform(0.8, 1.2) * spread, mat,
                    ch.p["head"], loc, rot=q, r2=0.004, seg=8)
            out.append(c)
    return out


# ---------------------------------------------------------------------
# Props
# ---------------------------------------------------------------------
def katana(name, parent, hilt_color, loc=(0, 0, 0), rot=(0, 0, 0), length=0.95):
    """Blade along local +Y from the grip."""
    steel = M("Steel", (0.85, 0.88, 0.92), rough=0.12, metal=1.0)
    gold = M("SwordGuard", C.COLORS["gold"], rough=0.3, metal=1.0)
    hilt = M(f"Hilt_{name}", hilt_color, rough=0.5)
    e = empty(name, parent, loc, rot)
    cyl(f"{name}_hilt", 0.028, 0.26, hilt, e, (0, -0.04, 0), rot=(R(90), 0, 0), seg=10)
    cyl(f"{name}_guard", 0.065, 0.02, gold, e, (0, 0.1, 0), rot=(R(90), 0, 0), seg=16)
    b = box(f"{name}_blade", (0.012, length, 0.05), steel, e, (0, 0.11 + length / 2, 0))
    return e


def climate_baton(parent, loc=(0, 0, 0), rot=(0, 0, 0)):
    blue = M("BatonBlue", (0.05, 0.25, 0.9), rough=0.3, metal=0.4)
    white = M("BatonWhite", (0.95, 0.95, 0.95), rough=0.3)
    e = empty("ClimaTact", parent, loc, rot)
    for i in range(5):
        cyl(f"Baton{i}", 0.026, 0.2, blue if i % 2 == 0 else white, e, (0, -0.4 + i * 0.2, 0),
            rot=(R(90), 0, 0), seg=12)
    for y in (-0.5, 0.5):
        sphere(f"BatonCap{y}", 0.04, blue, e, (0, y, 0), seg=12)
    return e


def tangerine(parent, loc=(0, 0, 0)):
    m = M("TangerineHand", (1.0, 0.38, 0.02), rough=0.4)
    leaf = M("LeafHand", (0.1, 0.45, 0.1), rough=0.5)
    t = sphere("Tangerine", 0.09, m, parent, loc, scale=(1, 1, 0.9))
    sphere("TangerineLeaf", 0.04, leaf, t, (0.02, 0, 0.085), scale=(1.4, 0.5, 0.3))
    return t


# ---------------------------------------------------------------------
# Characters
# ---------------------------------------------------------------------
def build_luffy(parent=None, loc=(0, 0, 0)):
    red = M("LuffyRed", C.COLORS["luffy_red"], rough=0.55)
    blue = M("LuffyShorts", (0.08, 0.22, 0.65), rough=0.7)
    sandal = M("Sandal", (0.35, 0.2, 0.08), rough=0.7)
    hair = M("HairBlack", (0.015, 0.015, 0.02), rough=0.55)
    sk = skin()
    ch = build_body("Luffy", dict(skin=sk, top=red, bottom=blue, shoe=sandal, thigh=blue, sleeve=red),
                    dict(torso_depth=0.68), parent, loc)
    # open vest: skin strip down the chest + X scar
    sp = ch.p["spine"]
    d = ch.dims
    strip = box("Luffy_chest", (0.15, 0.08, d["torso_h"] * 0.85), sk, sp,
                (0, d["chest_r"] * d["torso_depth"] * 0.82, d["torso_h"] * 0.55), subsurf=2)
    scar = M("Scar", (0.6, 0.2, 0.15), rough=0.5)
    for s in (-1, 1):
        box(f"Luffy_scar{s}", (0.012, 0.01, 0.16), scar, sp,
            (0, d["chest_r"] * d["torso_depth"] * 0.82 + 0.035, d["torso_h"] * 0.72), rot=(0, R(35 * s), 0))
    # shorts cuffs
    cuff = M("Cuff", (0.95, 0.95, 0.95), rough=0.6)
    for side in ("R", "L"):
        torus(f"Luffy_cuff_{side}", d["leg_r"] * 1.35, 0.02, cuff, ch.p[f"hip_{side}"], (0, 0, -d["thigh"] * 0.98))
    # yellow sash
    torus("Luffy_sash", d["waist_r"] * 1.15, 0.035, M("Sash", (0.95, 0.75, 0.1)), ch.p["hips"], (0, 0, 0.1))
    add_eyes(ch, brow_angle=14)
    add_mouth(ch, "grin")
    # scar under left eye
    loc, rot = face_point(ch, -24, -12, 0.0)
    box("Luffy_eyescar", (0.06, 0.01, 0.012), M("ScarDark", (0.15, 0.05, 0.03)), ch.p["head"], loc, rot=rot)
    hair_cap(ch, hair, scale=(1.05, 1.07, 0.98))
    spikes(ch, hair, n=11, length=0.14, z=0.05, rows=1, droop=0.9)
    # STRAW HAT
    straw = straw_mat()
    band = M("HatBand", C.COLORS["luffy_red"], rough=0.5)
    hr = d["head_r"]
    hat = empty("StrawHat", ch.p["head"], (0, -0.02, ch.head_center.z + hr * 0.62), rot=(R(-8), 0, 0))
    ch.p["hat"] = hat
    brim = cyl("Hat_brim", hr * 1.95, 0.025, straw, hat, (0, 0, 0), seg=40)
    add_subsurf(brim, 1)
    sphere("Hat_crown", hr * 1.02, straw, hat, (0, 0, 0.01), scale=(1, 1, 0.78))
    cyl("Hat_band", hr * 1.03, 0.07, band, hat, (0, 0, 0.05), seg=32)
    ch.parts["fist_R"].scale = (1.15, 1.2, 1.25)
    return ch


def build_zoro(parent=None, loc=(0, 0, 0)):
    white = M("ZoroShirt", (0.92, 0.92, 0.9), rough=0.7)
    green = M("ZoroGreen", C.COLORS["zoro_green"], rough=0.6)
    black = M("ZoroPants", (0.04, 0.04, 0.05), rough=0.6)
    boots = M("Boots", (0.02, 0.02, 0.02), rough=0.4)
    sk = skin()
    ch = build_body("Zoro", dict(skin=sk, top=white, bottom=black, shoe=boots, thigh=black, shin=black, sleeve=white),
                    dict(shoulder_w=0.31, chest_r=0.245, thigh=0.46, shin=0.44), parent, loc)
    d = ch.dims
    # haramaki
    cyl("Zoro_haramaki", d["waist_r"] * 1.18, 0.2, green, ch.p["spine"], (0, 0, 0.07),
        scale=(1, d["torso_depth"] * 1.1, 1))
    add_eyes(ch, iris=(0.02, 0.06, 0.02), brow_angle=20, squint=0.65)
    add_mouth(ch, "line")
    hair_cap(ch, green, scale=(1.04, 1.06, 0.92))
    spikes(ch, green, n=10, length=0.07, z=0.2, rows=2, rng_seed=4)
    # earrings
    gold = M("Earring", C.COLORS["gold"], rough=0.2, metal=1.0)
    for i in range(3):
        sphere(f"Zoro_earring{i}", 0.012, gold, ch.p["head"], (-d["head_r"] * 0.95, -0.01, d["head_r"] * (0.68 - i * 0.07)))
    # three swords: one in each hand + one in the mouth
    ch.p["sword_R"] = katana("Wado_R", ch.p["hand_R"], (0.95, 0.95, 0.95), (0, 0, -0.07), (R(0), 0, 0))
    ch.p["sword_L"] = katana("Sandai_L", ch.p["hand_L"], (0.6, 0.05, 0.05), (0, 0, -0.07), (R(0), 0, 0))
    loc, rot = face_point(ch, 0, -30, 0.02)
    ch.p["sword_M"] = katana("Shusui_M", ch.p["head"], (0.05, 0.05, 0.05), loc, (0, 0, R(-90)), length=0.85)
    return ch


def build_nami(parent=None, loc=(0, 0, 0)):
    top = stripes_mat("NamiTop", (0.95, 0.95, 0.95), (0.1, 0.3, 0.85), 14)
    jeans = M("NamiJeans", (0.25, 0.4, 0.75), rough=0.8)
    shoe = M("NamiShoe", (0.9, 0.5, 0.2), rough=0.5)
    hair = M("NamiHair", C.COLORS["nami_orange"], rough=0.5)
    sk = skin()
    ch = build_body("Nami", dict(skin=sk, top=top, bottom=jeans, shoe=shoe, thigh=jeans, sleeve=sk),
                    dict(shoulder_w=0.25, chest_r=0.2, waist_r=0.13, arm_r=0.055, leg_r=0.075,
                         torso_h=0.48, hand_r=0.065), parent, loc)
    add_eyes(ch, iris=(0.45, 0.2, 0.05), brow_angle=4, size=1.1)
    add_mouth(ch, "smile")
    hr = ch.dims["head_r"]
    hair_cap(ch, hair, scale=(1.08, 1.1, 1.02))
    # long hair falling down the back + bangs
    sphere("Nami_hairback", hr * 0.95, hair, ch.p["head"], (0, -hr * 0.45, ch.head_center.z - hr * 0.6),
           scale=(1.1, 0.6, 1.6))
    for i, sx in enumerate((-1, -0.4, 0.4, 1)):
        loc_, rot_ = face_point(ch, sx * 35, 38, -0.02)
        sphere(f"Nami_bang{i}", hr * 0.3, hair, ch.p["head"], loc_, scale=(0.7, 0.45, 1.0), rot=rot_)
    ch.p["baton"] = climate_baton(ch.p["hand_R"], (0, 0.02, -0.07))
    ch.p["tangerine"] = tangerine(ch.p["hand_L"], (0, 0.03, -0.17))
    return ch


def build_sanji(parent=None, loc=(0, 0, 0)):
    suit = M("SanjiSuit", (0.03, 0.03, 0.045), rough=0.45, coat=0.2)
    shirt = M("SanjiShirt", (0.15, 0.3, 0.75), rough=0.6)
    shoe = M("SanjiShoe", (0.02, 0.02, 0.02), rough=0.2)
    hair = M("SanjiHair", C.COLORS["sanji_blonde"], rough=0.45)
    sk = skin()
    ch = build_body("Sanji", dict(skin=sk, top=suit, bottom=suit, shoe=shoe, thigh=suit, shin=suit,
                                  sleeve=suit, upper=suit, fore=suit),
                    dict(shoulder_w=0.28, thigh=0.47, shin=0.46, leg_r=0.08), parent, loc)
    d = ch.dims
    sp = ch.p["spine"]
    box("Sanji_shirt", (0.12, 0.06, d["torso_h"] * 0.5), shirt, sp,
        (0, d["chest_r"] * d["torso_depth"] * 0.85, d["torso_h"] * 0.75), subsurf=2)
    box("Sanji_tie", (0.05, 0.03, d["torso_h"] * 0.42), M("Tie", (0.05, 0.05, 0.08)), sp,
        (0, d["chest_r"] * d["torso_depth"] * 0.9 + 0.02, d["torso_h"] * 0.72), subsurf=1)
    add_eyes(ch, iris=(0.05, 0.12, 0.35), brow_angle=10, skip_left=True)
    # curly eyebrow
    loc, rot = face_point(ch, 22, 24, 0.0)
    c = torus("Sanji_curl", 0.022, 0.006, M("BrowBlack", (0.02, 0.02, 0.02)), ch.p["head"], loc,
              arc=math.radians(320))
    c.rotation_euler = rot
    add_mouth(ch, "smirk")
    hr = d["head_r"]
    hair_cap(ch, hair, scale=(1.06, 1.08, 1.0))
    # fringe covering the left eye
    loc, rot = face_point(ch, -24, 12, 0.02)
    sphere("Sanji_fringe", hr * 0.42, hair, ch.p["head"], loc, scale=(1.0, 0.35, 1.15), rot=rot)
    # cigarette with glowing tip
    loc, rot = face_point(ch, 10, -30, 0.02)
    cig = cyl("Sanji_cig", 0.009, 0.11, M("Cig", (0.95, 0.95, 0.9)), ch.p["head"], loc,
              rot=(R(80), 0, R(25)), seg=8)
    tip = sphere("Sanji_cigtip", 0.011, mat_emit_fade("Ember", (1, 0.3, 0.05), 20), cig, (0, 0, 0.055), seg=8)
    tip.color = (1, 1, 1, 1)
    return ch


def build_chopper(parent=None, loc=(0, 0, 0)):
    fur = M("ChopperFur", (0.42, 0.22, 0.1), rough=0.85)
    shorts = M("ChopperShorts", (0.9, 0.35, 0.1), rough=0.7)
    hoof = M("Hoof", (0.15, 0.08, 0.04), rough=0.5)
    pink = M("ChopperHat", C.COLORS["chopper_pink"], rough=0.55)
    white = M("HatX", (0.98, 0.98, 0.98), rough=0.5)
    antler = M("Antler", (0.6, 0.42, 0.22), rough=0.6)
    nose = M("ChopperNose", (0.1, 0.35, 1.0), rough=0.15, emission=(0.1, 0.35, 1.0), emit_strength=0.6)
    ch = build_body("Chopper", dict(skin=fur, top=fur, bottom=shorts, shoe=hoof, thigh=shorts, shin=fur,
                                    upper=fur, fore=fur, hand=hoof),
                    dict(thigh=0.15, shin=0.13, leg_r=0.07, hip_w=0.09, torso_h=0.3, waist_r=0.17,
                         chest_r=0.17, torso_depth=0.9, shoulder_w=0.17, upper=0.13, fore=0.12,
                         arm_r=0.05, hand_r=0.06, neck=0.0, head_r=0.25, foot=(0.07, 0.13, 0.06)),
                    parent, loc)
    # Chopper's face is lighter tan
    face = M("ChopperFace", (0.75, 0.5, 0.3), rough=0.8)
    hr = ch.dims["head_r"]
    loc_, rot_ = face_point(ch, 0, -20, -0.04)
    sphere("Chopper_muzzle", hr * 0.6, face, ch.p["head"], loc_, scale=(1.1, 0.6, 0.85), rot=rot_)
    add_eyes(ch, iris=(0.02, 0.02, 0.02), size=1.35, brow_angle=-5, eye_el=8)
    add_mouth(ch, "smile")
    bpy.data.objects["Chopper_nose"].hide_render = True
    loc_, rot_ = face_point(ch, 0, -6, 0.04)
    sphere("Chopper_bluenose", hr * 0.12, nose, ch.p["head"], loc_, rot=rot_, scale=(1.2, 0.9, 0.9))
    # huge pink top hat with white X
    hat = empty("ChopperHat", ch.p["head"], (0, -0.02, ch.head_center.z + hr * 0.7), rot=(R(-6), 0, 0))
    ch.p["hat"] = hat
    cyl("ChopHat_brim", hr * 1.3, 0.04, pink, hat, (0, 0, 0), seg=32)
    cyl("ChopHat_top", hr * 0.95, hr * 1.25, pink, hat, (0, 0, hr * 0.62), seg=32, r2=hr * 1.0)
    for s in (-1, 1):
        box(f"ChopHat_X{s}", (0.04, 0.02, hr * 0.9), white, hat,
            (0, hr * 0.98, hr * 0.62), rot=(0, R(40 * s), 0))
    # antlers
    for sx in (-1, 1):
        a = cyl(f"Chop_antler{sx}", 0.025, 0.28, antler, ch.p["head"],
                (sx * hr * 0.75, -0.02, ch.head_center.z + hr * 0.75), rot=(0, R(sx * 55), 0), seg=8)
        cyl(f"Chop_antlerB{sx}", 0.02, 0.15, antler, a, (0, 0, 0.08), rot=(R(-45), R(-sx * 25), 0), seg=8)
    # ears
    for sx in (-1, 1):
        sphere(f"Chop_bigear{sx}", hr * 0.18, fur, ch.p["head"], (sx * hr * 1.0, 0, ch.head_center.z + hr * 0.35),
               scale=(1.2, 0.4, 0.6))
    return ch


BUILDERS = {
    "build_luffy": build_luffy, "build_zoro": build_zoro, "build_nami": build_nami,
    "build_sanji": build_sanji, "build_chopper": build_chopper,
}


# ---------------------------------------------------------------------
# POSES  (degrees).  Missing joints = 0.  'root_z' lifts the character.
# ---------------------------------------------------------------------
REST = {"sh_R": (0, -8, 0), "sh_L": (0, 8, 0), "el_R": (8, 0, 0), "el_L": (8, 0, 0)}

POSES = {
    "rest": REST,
    # Luffy: determined, fists clenched at the sides, slight lean forward
    "luffy_determined": {"sh_R": (5, -14, 0), "sh_L": (5, 14, 0), "el_R": (25, 0, 0), "el_L": (25, 0, 0),
                         "spine": (-5, 0, 0), "head": (4, 0, 0), "hip_R": (0, -5, 0), "hip_L": (0, 5, 0)},
    "luffy_fist_up": {"sh_R": (175, -10, 0), "el_R": (10, 0, 0), "sh_L": (20, 25, 0), "el_L": (70, 0, 0),
                      "spine": (3, 0, 0), "head": (6, 0, 0), "hip_R": (0, -8, 0), "hip_L": (0, 8, 0)},
    "luffy_windup": {"sh_R": (-55, -20, 0), "el_R": (95, 0, 0), "sh_L": (60, 25, 0), "el_L": (40, 0, 0),
                     "spine": (-10, 0, 25), "head": (8, 0, -15), "hip_R": (-10, -10, 0), "hip_L": (20, 10, 0),
                     "knee_R": (-25, 0, 0), "knee_L": (-15, 0, 0), "root_z": -0.08},
    "luffy_punch_up": {"sh_R": (178, 0, 0), "el_R": (0, 0, 0), "sh_L": (-30, 30, 0), "el_L": (60, 0, 0),
                       "spine": (10, 0, -8), "head": (35, 0, 0), "hip_R": (-5, -6, 0), "hip_L": (12, 8, 0),
                       "knee_L": (-15, 0, 0)},
    "luffy_victory": {"sh_R": (172, -12, 0), "el_R": (5, 0, 0), "sh_L": (30, 50, 0), "el_L": (95, 0, -30),
                      "spine": (4, 0, 4), "head": (4, 0, -6), "hip_R": (0, -10, 0), "hip_L": (0, 10, 0)},
    # Zoro: three-sword stance, arms out, blades forward
    "zoro_stance": {"sh_R": (55, -55, 0), "el_R": (35, 0, 0), "sh_L": (55, 55, 0), "el_L": (35, 0, 0),
                    "spine": (-10, 0, 0), "head": (8, 0, 0), "hip_R": (8, -12, 0), "hip_L": (-12, 12, 0),
                    "knee_R": (-20, 0, 0), "knee_L": (-10, 0, 0), "root_z": -0.06},
    "zoro_cross": {"sh_R": (80, 30, 0), "el_R": (60, 0, 0), "sh_L": (80, -30, 0), "el_L": (60, 0, 0),
                   "spine": (-12, 0, 0), "head": (10, 0, 0), "hip_R": (10, -14, 0), "hip_L": (-14, 14, 0),
                   "knee_R": (-25, 0, 0), "knee_L": (-10, 0, 0), "root_z": -0.08},
    # Nami: baton raised, tangerine held out
    "nami_pose": {"sh_R": (150, -30, 0), "el_R": (20, 0, 0), "sh_L": (60, 20, 0), "el_L": (50, 0, 0),
                  "spine": (3, 0, -8), "head": (4, 10, 8), "hip_R": (0, -6, 0), "hip_L": (8, 6, 0),
                  "knee_L": (-12, 0, 0)},
    # Sanji: high flame kick to the side, hands in pockets
    "sanji_kick": {"sh_R": (-10, -6, 0), "el_R": (-30, 0, 0), "sh_L": (-10, 6, 0), "el_L": (-30, 0, 0),
                   "spine": (0, 22, 0), "head": (0, -18, 0), "hip_R": (0, -100, 0), "knee_R": (-5, 0, 0),
                   "hip_L": (0, 8, 0)},
    "sanji_cool": {"sh_R": (-10, -6, 0), "el_R": (-30, 0, 0), "sh_L": (-10, 6, 0), "el_L": (-30, 0, 0),
                   "spine": (2, 0, 0), "head": (2, 0, 10), "hip_R": (0, -6, 0), "hip_L": (0, 6, 0)},
    # Chopper: jumping cheer
    "chopper_jump": {"sh_R": (160, -40, 0), "el_R": (10, 0, 0), "sh_L": (160, 40, 0), "el_L": (10, 0, 0),
                     "hip_R": (40, -10, 0), "knee_R": (-70, 0, 0), "hip_L": (40, 10, 0), "knee_L": (-70, 0, 0),
                     "head": (12, 0, 0), "root_z": 0.0},
    "chopper_happy": {"sh_R": (120, -50, 0), "el_R": (20, 0, 0), "sh_L": (120, 50, 0), "el_L": (20, 0, 0),
                      "head": (6, 0, 6)},
    # Crew finale (everyone): power stance looking at camera
    "crew_power": {"sh_R": (10, -22, 0), "sh_L": (10, 22, 0), "el_R": (30, 0, 0), "el_L": (30, 0, 0),
                   "hip_R": (0, -10, 0), "hip_L": (0, 10, 0), "head": (2, 0, 0)},
}

# Luffy looking up at the token in the sky, fists clenched (hope + hunger)
POSES["luffy_look_up"] = {"sh_R": (5, -14, 0), "sh_L": (5, 14, 0), "el_R": (35, 0, 0), "el_L": (35, 0, 0),
                          "spine": (6, 0, 0), "head": (28, 0, 0), "hip_R": (0, -6, 0), "hip_L": (0, 6, 0)}
# Gum-Gum grab: right arm aimed up-forward at the token (spine kept straight
# so the stretched arm points exactly at the target)
POSES["luffy_grab"] = {"sh_R": (148.5, 0, 0), "el_R": (0, 0, 0), "sh_L": (-35, 30, 0), "el_L": (60, 0, 0),
                       "spine": (0, 0, 0), "head": (30, 0, 0), "hip_R": (-5, -6, 0), "hip_L": (14, 8, 0),
                       "knee_L": (-18, 0, 0)}
# celebration: both arms up
POSES["cheer"] = {"sh_R": (165, -35, 0), "el_R": (15, 0, 0), "sh_L": (165, 35, 0), "el_L": (15, 0, 0),
                  "spine": (6, 0, 0), "head": (18, 0, 0), "hip_R": (0, -10, 0), "hip_L": (0, 10, 0)}
POSES["cheer_fist"] = {"sh_R": (170, -12, 0), "el_R": (10, 0, 0), "sh_L": (40, 45, 0), "el_L": (100, 0, 0),
                       "spine": (5, 0, 4), "head": (12, 0, -6), "hip_R": (0, -10, 0), "hip_L": (0, 10, 0)}
POSES["crew_look_up"] = dict(POSES["crew_power"], head=(32, 0, 0), spine=(8, 0, 0))

JOINTS = ["sh_R", "sh_L", "el_R", "el_L", "hip_R", "hip_L", "knee_R", "knee_L", "spine", "head"]


def key_pose(ch, frame, pose, interp="BEZIER"):
    """Keyframe every joint of `ch` to the given pose (name or dict)."""
    if isinstance(pose, str):
        pose = POSES[pose]
    for j in JOINTS:
        if j not in ch.p:
            continue
        r = pose.get(j, REST.get(j, (0, 0, 0)))
        key_rot(ch.p[j], frame, tuple(R(v) for v in r), interp)
    hz = ch.p["hips"]
    base = ch.dims["thigh"] + ch.dims["shin"] + ch.dims["foot"][2]
    key_loc(hz, frame, (0, 0, base + pose.get("root_z", 0.0)), interp)


def key_stretch(ch, side, frame, s, interp="BEZIER"):
    """GUM-GUM rubber stretch: elongate upper arm + forearm by factor s
    (thinner as it gets longer) while the fist keeps its size."""
    d = ch.dims
    thin = max(0.8, 1.0 / (s ** 0.2))
    key_scale(ch.parts[f"upper_{side}"], frame, (thin, thin, s), interp)
    key_scale(ch.parts[f"fore_{side}"], frame, (thin, thin, s), interp)
    key_loc(ch.p[f"el_{side}"], frame, (0, 0, -d["upper"] * s), interp)
    key_loc(ch.p[f"hand_{side}"], frame, (0, 0, -d["fore"] * s), interp)
