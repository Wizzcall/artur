"""
Stylized pirate caravel ("Fortnite-style" chunky proportions) with a
sheep figurehead, straw-hat sail, flag, tangerine trees and barrels.
Everything is parented to the empty 'Ship' which bobs on the waves.
Bow points to +Y.  Deck height = DECK_Z.
"""
import math
import bmesh
import bpy
from mathutils import Vector

import config as C
from .utils import (empty, obj_from_mesh, mat_basic, mat_image, sphere, cyl, box,
                    torus, link, key, add_subsurf, mesh_plane)

DECK_Z = 2.4
RAIL_Z = 3.05
STERN_Y, BOW_Y = -10.5, 10.0


def half_width(y):
    """Hull half-width as a function of Y (bow narrows to a point)."""
    t = (y - STERN_Y) / (BOW_Y - STERN_Y)              # 0 stern .. 1 bow
    w = 4.4 * math.sin(math.pi * (0.25 + 0.75 * t)) ** 0.7
    if t < 0.08:                                       # flat transom
        w = max(w, 3.2)
    return max(w, 0.05)


def _hull_mesh():
    bm = bmesh.new()
    nY, nP = 34, 14
    rings = []
    for i in range(nY):
        y = STERN_Y + (BOW_Y - STERN_Y) * i / (nY - 1)
        w = half_width(y)
        t = (y - STERN_Y) / (BOW_Y - STERN_Y)
        keel = -1.9 + 1.2 * max(0, t - 0.75) / 0.25        # keel rises at bow
        top = RAIL_Z + 0.9 * max(0, t - 0.85) / 0.15 + 0.7 * max(0, 0.12 - t) / 0.12
        ring = []
        for j in range(nP):
            a = math.pi * j / (nP - 1)                        # 0..pi  left->right
            x = -math.cos(a) * w
            s = math.sin(a)
            z = top - (top - keel) * (s ** 0.55) if 0 < j < nP - 1 else top
            ring.append(bm.verts.new((x, y, z)))
        rings.append(ring)
    for i in range(nY - 1):
        for j in range(nP - 1):
            bm.faces.new((rings[i][j], rings[i][j + 1], rings[i + 1][j + 1], rings[i + 1][j]))
    bm.faces.new(list(reversed(rings[0])))      # transom
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("Hull")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


def _deck_mesh():
    bm = bmesh.new()
    pts = []
    n = 40
    for i in range(n):
        y = STERN_Y + 0.3 + (BOW_Y - 0.4 - STERN_Y - 0.3) * i / (n - 1)
        pts.append((half_width(y) - 0.18, y))
    verts = [bm.verts.new((x, y, DECK_Z)) for x, y in pts]
    verts += [bm.verts.new((-x, y, DECK_Z)) for x, y in reversed(pts)]
    bm.faces.new(verts)
    me = bpy.data.meshes.new("Deck")
    bm.to_mesh(me)
    bm.free()
    return me


def _wood_mat(name, c1, c2, scale=6.0):
    """Wood planks: wave texture bands mixing two browns."""
    m = mat_basic(name, c1, rough=0.6)
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "Z"
    wave.inputs["Scale"].default_value = scale
    wave.inputs["Distortion"].default_value = 1.5
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(tc.outputs["Object"], wave.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*c1, 1)
    ramp.color_ramp.elements[1].color = (*c2, 1)
    nt.links.new(wave.outputs["Fac"], ramp.inputs[0])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    return m


def _hull_paint():
    """Hull colors by height: dark wood below the waterline stripe,
    a gold stripe, then cream paint up to the rail (Going-Merry vibe)."""
    m = mat_basic("HullPaint", (0.9, 0.86, 0.78), rough=0.45)
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -2.0
    mr.inputs["From Max"].default_value = 4.0
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.interpolation = "CONSTANT"
    cr.elements[0].position = 0.0
    cr.elements[0].color = (0.22, 0.09, 0.04, 1)          # dark wood
    cr.elements[1].position = (1.05 + 2) / 6
    cr.elements[1].color = (*C.COLORS["gold"], 1)         # gold stripe
    e = cr.elements.new((1.3 + 2) / 6)
    e.color = (0.9, 0.86, 0.78, 1)                        # cream paint
    e = cr.elements.new((2.75 + 2) / 6)
    e.color = (0.35, 0.16, 0.06, 1)                       # wooden rail band
    nt.links.new(mr.outputs["Result"], ramp.inputs[0])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    return m


def _sail(name, w, h, mat, parent, loc, bulge=0.8):
    bm = bmesh.new()
    nx, nz = 12, 12
    vs = []
    for j in range(nz + 1):
        row = []
        for i in range(nx + 1):
            u, v = i / nx, j / nz
            x = (u - 0.5) * w * (1 - 0.12 * v)
            z = -v * h
            y = bulge * math.sin(math.pi * u) * math.sin(math.pi * (0.15 + 0.85 * v))
            row.append(bm.verts.new((x, y, z)))
        vs.append(row)
    uv_l = bm.loops.layers.uv.new("UVMap")
    for j in range(nz):
        for i in range(nx):
            f = bm.faces.new((vs[j][i], vs[j][i + 1], vs[j + 1][i + 1], vs[j + 1][i]))
            for loop, (a, bb) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
                loop[uv_l].uv = (a / nx, 1 - bb / nz)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = obj_from_mesh(name, me, mat, parent, loc)
    s = ob.modifiers.new("Solid", "SOLIDIFY")
    s.thickness = 0.03
    return ob


def build_ship(tex, end_frame):
    root = empty("Ship", size=2)
    wood = _wood_mat("HullWood", (0.30, 0.13, 0.05), (0.42, 0.20, 0.08), 7.0)
    deck_wood = _wood_mat("DeckWood", (0.55, 0.36, 0.18), (0.65, 0.45, 0.24), 3.0)
    white_hull = mat_basic("HullPaint", (0.92, 0.88, 0.80), rough=0.45)
    gold = mat_basic("ShipGold", C.COLORS["gold"], rough=0.25, metal=1.0)
    dark = mat_basic("DarkWood", (0.12, 0.06, 0.03), rough=0.6)
    sail_mat = mat_image("SailMat", tex["sail"], rough=0.8)
    plain_sail = mat_basic("SailPlain", (0.93, 0.90, 0.82), rough=0.85)
    flag_mat = mat_image("FlagMat", tex["flag"], rough=0.8)
    for m in (sail_mat, plain_sail, flag_mat):
        try:
            m.node_tree.nodes["Principled BSDF"].inputs["Subsurface Weight"].default_value = 0.0
        except Exception:
            pass

    hull = obj_from_mesh("Hull", _hull_mesh(), _hull_paint(), root)
    add_subsurf(hull, 1)
    hull.modifiers.new("Solid", "SOLIDIFY").thickness = 0.12
    deck = obj_from_mesh("Deck", _deck_mesh(), deck_wood, root)

    # gold rail along the hull edge
    curve = bpy.data.curves.new("RailCurve", "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = 0.09
    curve.bevel_resolution = 3
    sp = curve.splines.new("POLY")
    pts = []
    n = 40
    for i in range(n):
        y = STERN_Y + 0.05 + (BOW_Y - 0.1 - STERN_Y) * i / (n - 1)
        t = (y - STERN_Y) / (BOW_Y - STERN_Y)
        z = RAIL_Z + 0.9 * max(0, t - 0.85) / 0.15 + 0.7 * max(0, 0.12 - t) / 0.12
        pts.append((half_width(y) * 0.99, y, z + 0.04))
    full = pts + [(-x, y, z) for x, y, z in reversed(pts)]
    sp.points.add(len(full) - 1)
    for p, co in zip(sp.points, full):
        p.co = (*co, 1)
    sp.use_cyclic_u = True
    rail = bpy.data.objects.new("Rail", curve)
    link(rail)
    rail.parent = root
    curve.materials.append(gold)
    # --- masts, yards, sails ------------------------------------------
    main_mast = cyl("MainMast", 0.22, 15, dark, root, (0, -1.2, DECK_Z + 7.5), r2=0.15)
    fore_mast = cyl("ForeMast", 0.18, 10, dark, root, (0, 4.2, DECK_Z + 5.0), r2=0.12)
    for nm, z, w in (("YardMainTop", DECK_Z + 13.0, 8.5), ("YardMainLow", DECK_Z + 7.6, 10.0)):
        cyl(nm, 0.12, w, dark, root, (0, -1.0, z), rot=(0, math.pi / 2, 0))
    cyl("YardFore", 0.1, 6.5, dark, root, (0, 4.35, DECK_Z + 9.2), rot=(0, math.pi / 2, 0))
    _sail("MainSail", 9.6, 5.0, sail_mat, root, (0, -1.0, DECK_Z + 7.55), bulge=0.9)
    _sail("TopSail", 8.0, 4.4, plain_sail, root, (0, -1.0, DECK_Z + 12.95), bulge=0.7)
    _sail("ForeSail", 6.2, 4.5, plain_sail, root, (0, 4.35, DECK_Z + 9.15), bulge=0.6)
    # crow's nest
    cyl("CrowsNest", 0.75, 0.7, wood, root, (0, -1.2, DECK_Z + 14.0))
    # flag (waving)
    flag = obj_from_mesh("Flag", mesh_plane("FlagMesh", 2.8, 1.9), flag_mat, root,
                         (1.45, -1.2, DECK_Z + 15.6), rot=(math.pi / 2, 0, 0))
    sub = flag.modifiers.new("Sub", "SUBSURF")
    sub.subdivision_type = "SIMPLE"
    sub.levels = sub.render_levels = 4
    wv = flag.modifiers.new("Wave", "WAVE")
    wv.use_x = True
    wv.use_y = False
    wv.height = 0.18
    wv.width = 1.1
    wv.speed = 0.12
    wv.start_position_x = -1.4
    wv.use_normal = True
    wv.use_normal_x = wv.use_normal_y = False
    wv.use_normal_z = True

    # bowsprit
    cyl("Bowsprit", 0.16, 6, dark, root, (0, BOW_Y + 1.6, RAIL_Z + 1.6), rot=(math.radians(-65), 0, 0), r2=0.08)

    # --- sheep figurehead ------------------------------------------------
    wool = mat_basic("Wool", (0.95, 0.94, 0.9), rough=0.9)
    face = mat_basic("SheepFace", (0.88, 0.8, 0.7), rough=0.6)
    horn = mat_basic("Horn", (0.85, 0.7, 0.45), rough=0.4)
    eye = mat_basic("SheepEye", C.COLORS["black"], rough=0.2)
    fh = empty("Figurehead", root, (0, BOW_Y + 0.35, RAIL_Z + 0.85))
    import random
    rnd = random.Random(3)
    for i in range(14):
        a = 2 * math.pi * i / 14
        sphere(f"WoolPuff{i}", 0.42, wool, fh,
               (math.cos(a) * 0.55, -0.15 + rnd.uniform(-0.1, 0.1), math.sin(a) * 0.55), seg=16)
    sphere("WoolCore", 0.7, wool, fh, (0, -0.1, 0), seg=24)
    sphere("SheepMuzzle", 0.48, face, fh, (0, 0.55, -0.1), scale=(0.9, 1.1, 0.85))
    for sx in (-1, 1):
        sphere(f"SheepEye{sx}", 0.08, eye, fh, (sx * 0.2, 0.95, 0.12))
        h = torus(f"SheepHorn{sx}", 0.28, 0.09, horn, fh, (sx * 0.6, 0.15, 0.25),
                  rot=(0, math.pi / 2, 0), arc=math.radians(300))

    # --- deck props ---------------------------------------------------------
    barrel_m = _wood_mat("Barrel", (0.45, 0.25, 0.1), (0.35, 0.18, 0.07), 10)
    for i, (x, y) in enumerate(((3.3, -4.5), (2.6, -5.2), (-3.2, -5.0), (3.4, -3.5))):
        b = cyl(f"Barrel{i}", 0.42, 0.95, barrel_m, root, (x, y, DECK_Z + 0.48))
        for z in (-0.3, 0.3):
            torus(f"BarrelHoop{i}{z}", 0.43, 0.03, dark, b, (0, 0, z))
    # stern cabin
    cabin = box("Cabin", (6.0, 3.2, 1.8), wood, root, (0, -8.2, DECK_Z + 0.9), bevel=0.08)
    box("CabinRoof", (6.4, 3.6, 0.2), gold, root, (0, -8.2, DECK_Z + 1.9), bevel=0.04)
    # tangerine trees (Nami!)
    leaf = mat_basic("Leaf", (0.08, 0.35, 0.08), rough=0.7)
    tang = mat_basic("Tangerine", (1.0, 0.38, 0.02), rough=0.4)
    trunk = mat_basic("Trunk", (0.25, 0.14, 0.06), rough=0.8)
    for i, x in enumerate((-2.0, 0.0, 2.0)):
        base = (x, -8.0, DECK_Z + 1.9)
        cyl(f"TreeTrunk{i}", 0.08, 0.9, trunk, root, (x, -8.0, base[2] + 0.45))
        cr = sphere(f"TreeCrown{i}", 0.6, leaf, root, (x, -8.0, base[2] + 1.2), seg=16)
        for k in range(6):
            a = 2 * math.pi * k / 6 + i
            sphere(f"Tang{i}{k}", 0.11, tang, cr,
                   (math.cos(a) * 0.55, math.sin(a) * 0.55, rnd.uniform(-0.3, 0.3)), seg=12)

    # ship bob (gentle roll / pitch / heave)
    for f in range(1, end_frame + 1, 10):
        t = f / C.FPS
        key(root, "location", f, (0, 0, 0.12 * math.sin(t * 1.1)))
        key(root, "rotation_euler", f, (0.025 * math.sin(t * 0.9 + 1),
                                        0.03 * math.sin(t * 0.7), 0))
    return root
