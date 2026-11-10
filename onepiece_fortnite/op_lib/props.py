"""
Hero props: the Pirate Shop Token, the giant treasure chest, V-Bucks
coins and glowing One Piece symbols (used by the treasure rain).
"""
import math
import bpy
from mathutils import Vector

import config as C
from .utils import (empty, cyl, box, torus, sphere, obj_from_mesh, mesh_plane, mesh_cylinder,
                    mat_basic, mat_image, mat_emit_fade, add_bevel, link, no_shadow, key)

R = math.radians


def gold_mat():
    return mat_basic("Gold", C.COLORS["gold"], rough=0.18, metal=1.0)


def glow_sphere_mat(name, color, strength=2.0, power=3.0):
    """Soft halo: bright in the middle of the silhouette, fading to the
    edge (inverted fresnel).  Opacity via Object Info > Alpha."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.5
    inv = nt.nodes.new("ShaderNodeMath"); inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    nt.links.new(lw.outputs["Facing"], inv.inputs[1])
    pw = nt.nodes.new("ShaderNodeMath"); pw.operation = "POWER"
    pw.inputs[1].default_value = power
    nt.links.new(inv.outputs[0], pw.inputs[0])
    info = nt.nodes.new("ShaderNodeObjectInfo")
    m1 = nt.nodes.new("ShaderNodeMath"); m1.operation = "MULTIPLY"
    nt.links.new(pw.outputs[0], m1.inputs[0])
    nt.links.new(info.outputs["Alpha"], m1.inputs[1])
    m2 = nt.nodes.new("ShaderNodeMath"); m2.operation = "MULTIPLY"
    m2.inputs[1].default_value = strength
    nt.links.new(m1.outputs[0], m2.inputs[0])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1)
    nt.links.new(m2.outputs[0], em.inputs["Strength"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(tr.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs["Surface"])
    return m


def coin(name, tex_path, radius=1.0, thick=0.16, rim_mat=None, face_emit=0.4, parent=None, loc=(0, 0, 0)):
    """A coin standing up: faces look along +Y / -Y."""
    root = empty(name, parent, loc)
    rim_mat = rim_mat or gold_mat()
    body = cyl(f"{name}_body", radius, thick, rim_mat, root, rot=(R(90), 0, 0), seg=64)
    add_bevel(body, 0.03, 2)
    torus(f"{name}_rim", radius * 0.98, thick * 0.38, rim_mat, root, rot=(R(90), 0, 0), seg=64)
    face_m = mat_image(f"{name}_FaceMat", tex_path, rough=0.25, metal=0.6, emit=face_emit,
                       alpha=True, bump=0.4)
    for sgn in (1, -1):
        f = obj_from_mesh(f"{name}_face{sgn}", mesh_plane(f"{name}_facemesh", 2 * radius * 0.97,
                                                          2 * radius * 0.97),
                          face_m, root, (0, sgn * (thick / 2 + 0.006), 0),
                          # plane normal -> +/-Y, texture "up" stays +Z on both faces
                          rot=(R(90), 0, R(180) if sgn > 0 else 0))
    return root


def build_token(tex, loc):
    """The Pirate Shop Token + halo + its own light."""
    tok = coin("PirateToken", tex["token"], 1.0, 0.18, face_emit=0.6, loc=loc)
    halo = sphere("TokenHalo", 2.6, glow_sphere_mat("TokenHaloMat", (1.0, 0.65, 0.2), 1.6, 3.5), tok)
    halo.color = (1, 1, 1, 0.0)
    no_shadow(halo)
    ld = bpy.data.lights.new("TokenLight", "POINT")
    ld.color = (1.0, 0.75, 0.35)
    ld.energy = 0
    ld.shadow_soft_size = 0.8
    lo = bpy.data.objects.new("TokenLight", ld)
    link(lo)
    lo.parent = tok
    lo.location = (0, 1.4, 0.3)
    return tok, halo, ld


def build_chest(loc):
    """Giant treasure chest.  Returns (root, lid_pivot, light, inner_glow)."""
    wood = mat_basic("ChestWood", (0.45, 0.12, 0.05), rough=0.55, coat=0.3)
    gold = gold_mat()
    root = empty("TreasureChest", None, loc, size=1.5)
    W, D, H = 3.2, 2.0, 1.6
    body = box("Chest_body", (W, D, H), wood, root, (0, 0, H / 2), bevel=0.06)
    # gold bands & corners
    for x in (-W / 2 + 0.25, 0, W / 2 - 0.25):
        box(f"Chest_band{x}", (0.22, D + 0.06, H + 0.04), gold, root, (x, 0, H / 2), bevel=0.03)
    for z in (0.08, H - 0.05):
        box(f"Chest_rimz{z}", (W + 0.06, D + 0.06, 0.12), gold, root, (0, 0, z), bevel=0.02)
    # lid hinge at the back top edge
    hinge = empty("Chest_hinge", root, (0, -D / 2, H))
    lid = cyl("Chest_lid", D / 2, W, wood, hinge, (0, D / 2, 0), rot=(0, R(90), 0), seg=32)
    # remove lower half of the lid cylinder via scale trick: squash a bit
    lid.scale = (0.75, 1, 1)
    for x in (-W / 2 + 0.25, 0, W / 2 - 0.25):
        t = torus(f"Chest_lidband{x}", D / 2 + 0.03, 0.07, gold, hinge, (x, D / 2, 0),
                  rot=(0, R(90), 0), arc=math.pi)
        t.scale = (1, 0.78, 1)
        t.rotation_euler = (R(90), R(0), R(90))
    box("Chest_lock", (0.4, 0.15, 0.5), gold, root, (0, D / 2 + 0.06, H - 0.15), bevel=0.04)
    # treasure inside (gold heap) + light
    sphere("Chest_gold", 1.2, gold, root, (0, 0, H - 0.15), scale=(1.15, 0.7, 0.35))
    glow = sphere("Chest_glow", 2.2, glow_sphere_mat("ChestGlowMat", (1.0, 0.75, 0.2), 4.0, 2.0),
                  root, (0, 0, H + 0.3))
    glow.color = (1, 1, 1, 0.3)
    no_shadow(glow)
    ld = bpy.data.lights.new("ChestLight", "POINT")
    ld.color = (1.0, 0.75, 0.3)
    ld.energy = 0
    ld.shadow_soft_size = 1.5
    lo = bpy.data.objects.new("ChestLight", ld)
    link(lo)
    lo.parent = root
    lo.location = (0, 0, H + 1.0)
    return root, hinge, ld, glow


def build_glider(name, tex, loc=(0, 0, -500)):
    """Mini 'Going Merry' glider: a small hull with a sheep head hanging
    under a big curved straw-hat wing."""
    root = empty(name, None, loc)
    wood = bpy.data.materials.get("HullWood") or mat_basic("GliderWood", (0.4, 0.2, 0.08))
    wool = bpy.data.materials.get("Wool") or mat_basic("GliderWool", (0.95, 0.94, 0.9), rough=0.9)
    hull = mat_basic("GliderHull", (0.92, 0.88, 0.8), rough=0.45)
    wing_m = mat_image("GliderWingMat", tex["sail"], rough=0.7)
    # wing: subdivided plane bent into an arc
    me = mesh_plane(f"{name}_wingmesh", 2.4, 1.1)
    wing = obj_from_mesh(f"{name}_wing", me, wing_m, root, (0, 0, 1.0))
    sub = wing.modifiers.new("Sub", "SUBSURF")
    sub.subdivision_type = "SIMPLE"
    sub.levels = sub.render_levels = 3
    bend = wing.modifiers.new("Bend", "SIMPLE_DEFORM")
    bend.deform_method = "BEND"
    bend.deform_axis = "Y"
    bend.angle = R(-70)
    wing.modifiers.new("Solid", "SOLIDIFY").thickness = 0.03
    for sx in (-1, 1):
        cyl(f"{name}_rope{sx}", 0.01, 1.1, wood, root, (sx * 0.55, 0, 0.5), rot=(0, R(-sx * 25), 0), seg=6)
    body = sphere(f"{name}_hull", 0.35, hull, root, (0, 0, 0), scale=(0.75, 1.5, 0.55))
    sphere(f"{name}_sheep", 0.2, wool, root, (0, 0.5, 0.12))
    sphere(f"{name}_face", 0.12, mat_basic("GliderFace", (0.88, 0.8, 0.7)), root, (0, 0.66, 0.1))
    return root


def build_rain_templates(tex):
    """Return mesh/material 'templates' for the treasure rain.  Rain items
    are cheap linked duplicates of these."""
    temps = {}
    temps["vbuck"] = coin("TPL_VBuck", tex["vbuck"], 0.45, 0.08,
                          rim_mat=mat_basic("VBuckRim", (0.15, 0.45, 1.0), rough=0.25, metal=0.8),
                          face_emit=0.8, loc=(0, 0, -500))
    temps["token"] = coin("TPL_Token", tex["token"], 0.5, 0.09, face_emit=0.8, loc=(0, 0, -500))
    sym = mat_image("SymbolGlow", tex["jolly"], rough=0.5, emit=3.0, alpha=True, fade=True)
    temps["symbol_mesh"] = mesh_plane("SymbolMesh", 1.3, 1.3)
    temps["symbol_mat"] = sym
    # free skin cards (rounded-corner cards with alpha) - 3 rarities
    temps["card_mesh"] = mesh_plane("CardMesh", 1.1, 1.55)
    temps["card_mats"] = [mat_image(f"CardMat_{st}", tex[f"card_{st}"], rough=0.35, emit=1.2, alpha=True)
                          for st in ("legendary", "epic", "rare")]
    temps["glider"] = build_glider("TPL_Glider", tex)
    return temps


def build_empty_chest(name, loc, rot_z=0.0, scale=0.45):
    """Small opened, EMPTY chest drifting in the storm (the grind...)."""
    wood = mat_basic("OldChestWood", (0.22, 0.1, 0.05), rough=0.7)
    iron = mat_basic("OldChestIron", (0.25, 0.24, 0.22), rough=0.4, metal=1.0)
    root = empty(name, None, loc, (0, 0, rot_z))
    root.scale = (scale, scale, scale)
    W, D, H = 2.4, 1.6, 1.2
    box(f"{name}_body", (W, D, H), wood, root, (0, 0, H / 2), bevel=0.05)
    box(f"{name}_inner", (W - 0.25, D - 0.25, 0.1), mat_basic("ChestDark", (0.02, 0.01, 0.01)), root,
        (0, 0, H - 0.04))
    for x in (-W / 2 + 0.2, W / 2 - 0.2):
        box(f"{name}_band{x}", (0.16, D + 0.04, H + 0.02), iron, root, (x, 0, H / 2), bevel=0.02)
    hinge = empty(f"{name}_hinge", root, (0, -D / 2, H), (R(-115), 0, 0))
    box(f"{name}_lid", (W, D, 0.25), wood, hinge, (0, D / 2, 0.12), bevel=0.05)
    return root
