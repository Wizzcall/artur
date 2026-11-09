"""
Low-level helpers: keyframes, primitives, materials, collections.
Everything here is generic - no story logic.
"""
import math
import bpy
import bmesh
from mathutils import Vector, Matrix, Euler

# ---------------------------------------------------------------------
# KEYFRAMES
# ---------------------------------------------------------------------
# Blender uses the user preference for the interpolation of newly
# inserted keys - we switch it on the fly so every helper call can
# choose its own curve ('BEZIER' = ease in/out, 'LINEAR', 'CONSTANT'
# = hard cut, 'BACK' / 'ELASTIC' = overshoot pop, 'EXPO' = snappy).
_PREFS = bpy.context.preferences.edit


def key(target, path, frame, value=None, interp="BEZIER", index=-1):
    """Set `target.path = value` (if given) and insert a keyframe."""
    if value is not None:
        if index >= 0:
            getattr(target, path)[index] = value
        else:
            setattr(target, path, value)
    _PREFS.keyframe_new_interpolation_type = interp
    target.keyframe_insert(data_path=path, frame=frame, index=index)
    _PREFS.keyframe_new_interpolation_type = "BEZIER"


def key_loc(obj, frame, loc, interp="BEZIER"):
    key(obj, "location", frame, Vector(loc), interp)


def key_rot(obj, frame, rot, interp="BEZIER"):
    key(obj, "rotation_euler", frame, Euler(rot), interp)


def key_scale(obj, frame, s, interp="BEZIER"):
    if isinstance(s, (int, float)):
        s = (s, s, s)
    key(obj, "scale", frame, Vector(s), interp)


def key_alpha(obj, frame, a, interp="BEZIER"):
    """Fade objects whose material reads Object Info > Alpha."""
    c = list(obj.color)
    c[3] = a
    key(obj, "color", frame, c, interp)


def key_visible(obj, frame, visible):
    """Hard show/hide (render visibility) at a frame."""
    key(obj, "hide_render", frame, not visible, "CONSTANT")
    key(obj, "hide_viewport", frame, not visible, "CONSTANT")


def pop_in(obj, frame, dur=8, final_scale=1.0, interp="BACK", start=0.001):
    """Scale-from-zero 'pop' with an overshoot.  (The interpolation of a
    key controls the segment that FOLLOWS it, so BACK on the first key
    gives the overshoot.)"""
    key_scale(obj, frame, start, interp)
    key_scale(obj, frame + dur, final_scale, "BEZIER")


# ---------------------------------------------------------------------
# COLLECTIONS
# ---------------------------------------------------------------------
def collection(name, parent=None):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(col)
    return col


_ACTIVE_COL = [None]


def set_active_collection(col):
    _ACTIVE_COL[0] = col


def link(obj):
    col = _ACTIVE_COL[0] or bpy.context.scene.collection
    col.objects.link(obj)
    return obj


# ---------------------------------------------------------------------
# PRIMITIVES (bmesh based - fast, no operators, no context needed)
# ---------------------------------------------------------------------
def _mesh_from_bm(bm, name, smooth=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return me


def mesh_sphere(name, r=1.0, seg=32, rings=16):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=r)
    return _mesh_from_bm(bm, name)


def mesh_ico(name, r=1.0, subdiv=2, smooth=True):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=r)
    return _mesh_from_bm(bm, name, smooth)


def mesh_cylinder(name, r=1.0, depth=1.0, seg=24, r2=None, top_origin=False, smooth=True):
    """Cylinder / cone along Z.  top_origin=True puts the origin at the top
    cap so the object hangs downwards (perfect for limbs)."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg,
                          radius1=r, radius2=r if r2 is None else r2, depth=depth)
    if top_origin:
        bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, -depth / 2))
    me = _mesh_from_bm(bm, name, smooth)
    return me


def mesh_cube(name, size=(1, 1, 1)):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    return _mesh_from_bm(bm, name, smooth=False)


def mesh_torus(name, R=1.0, r=0.1, seg=48, ring_seg=12, arc=2 * math.pi):
    """Torus (or partial torus when arc < 2pi) in the XY plane."""
    bm = bmesh.new()
    full = arc >= 2 * math.pi - 1e-4
    nseg = seg if full else seg + 1
    rings = []
    for i in range(nseg):
        a = arc * i / seg
        c = Vector((math.cos(a) * R, math.sin(a) * R, 0))
        outward = Vector((math.cos(a), math.sin(a), 0))
        ring = []
        for j in range(ring_seg):
            b = 2 * math.pi * j / ring_seg
            p = c + outward * (math.cos(b) * r) + Vector((0, 0, math.sin(b) * r))
            ring.append(bm.verts.new(p))
        rings.append(ring)
    pairs = range(nseg) if full else range(nseg - 1)
    for i in pairs:
        r1, r2 = rings[i], rings[(i + 1) % nseg]
        for j in range(ring_seg):
            bm.faces.new((r1[j], r2[j], r2[(j + 1) % ring_seg], r1[(j + 1) % ring_seg]))
    if not full:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _mesh_from_bm(bm, name)


def mesh_plane(name, sx=1.0, sy=1.0):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
    bmesh.ops.scale(bm, vec=(sx, sy, 1), verts=bm.verts)
    me = _mesh_from_bm(bm, name, smooth=False)
    # simple 0..1 UVs
    uv = me.uv_layers.new(name="UVMap")
    for loop in me.loops:
        co = me.vertices[loop.vertex_index].co
        uv.data[loop.index].uv = (co.x / sx + 0.5, co.y / sy + 0.5)
    return me


def obj_from_mesh(name, me, mat=None, parent=None, loc=(0, 0, 0),
                  rot=(0, 0, 0), scale=(1, 1, 1)):
    ob = bpy.data.objects.new(name, me)
    link(ob)
    if mat is not None:
        if me.materials:
            me.materials[0] = mat
        else:
            me.materials.append(mat)
    ob.parent = parent
    ob.location = loc
    ob.rotation_euler = rot
    ob.scale = scale if not isinstance(scale, (int, float)) else (scale,) * 3
    return ob


def empty(name, parent=None, loc=(0, 0, 0), rot=(0, 0, 0), size=0.2):
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_size = size
    link(ob)
    ob.parent = parent
    ob.location = loc
    ob.rotation_euler = rot
    return ob


# Convenience one-liners used heavily by the character builders -------
def sphere(name, r, mat, parent=None, loc=(0, 0, 0), scale=(1, 1, 1), rot=(0, 0, 0), seg=32):
    return obj_from_mesh(name, mesh_sphere(name, r, seg, max(8, seg // 2)), mat, parent, loc, rot, scale)


def cyl(name, r, depth, mat, parent=None, loc=(0, 0, 0), rot=(0, 0, 0),
        scale=(1, 1, 1), r2=None, top_origin=False, seg=24):
    return obj_from_mesh(name, mesh_cylinder(name, r, depth, seg, r2, top_origin), mat,
                         parent, loc, rot, scale)


def box(name, size, mat, parent=None, loc=(0, 0, 0), rot=(0, 0, 0), bevel=0.0, subsurf=0):
    ob = obj_from_mesh(name, mesh_cube(name, size), mat, parent, loc, rot)
    if bevel > 0:
        m = ob.modifiers.new("Bevel", "BEVEL")
        m.width = bevel
        m.segments = 3
        m.limit_method = "NONE"
        for p in ob.data.polygons:
            p.use_smooth = True
    if subsurf:
        m = ob.modifiers.new("Sub", "SUBSURF")
        m.levels = m.render_levels = subsurf
        for p in ob.data.polygons:
            p.use_smooth = True
    return ob


def torus(name, R, r, mat, parent=None, loc=(0, 0, 0), rot=(0, 0, 0), arc=2 * math.pi, seg=48):
    return obj_from_mesh(name, mesh_torus(name, R, r, seg, 12, arc), mat, parent, loc, rot)


def look_at_rotation(src, dst, up_axis="Y", track="-Z"):
    d = Vector(dst) - Vector(src)
    return d.to_track_quat(track, up_axis).to_euler()


def only_camera_visible(ob):
    """Overlay objects (HUD text, flashes) - invisible to light rays & shadows."""
    for attr in ("visible_diffuse", "visible_glossy", "visible_transmission",
                 "visible_volume_scatter", "visible_shadow"):
        if hasattr(ob, attr):
            setattr(ob, attr, False)


def no_shadow(ob):
    if hasattr(ob, "visible_shadow"):
        ob.visible_shadow = False


# ---------------------------------------------------------------------
# MATERIALS
# ---------------------------------------------------------------------
def _new_mat(name):
    m = bpy.data.materials.get(name)
    if m:
        return m, False
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, True


def pbsdf(m):
    return next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")


def mat_basic(name, color, rough=0.5, metal=0.0, emission=None, emit_strength=0.0,
              coat=0.0, spec=0.5):
    """Standard stylized PBR material."""
    m, new = _new_mat(name)
    if not new:
        return m
    b = pbsdf(m)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if "Specular IOR Level" in b.inputs:
        b.inputs["Specular IOR Level"].default_value = spec
    if coat and "Coat Weight" in b.inputs:
        b.inputs["Coat Weight"].default_value = coat
    if emission is not None:
        b.inputs["Emission Color"].default_value = (*emission, 1)
        b.inputs["Emission Strength"].default_value = emit_strength
    m.diffuse_color = (*color, 1)
    return m


def mat_emit_fade(name, color, strength=5.0, use_obj_alpha=True, additive=True):
    """Pure glowing material whose opacity follows Object Info > Alpha
    (animate with key_alpha).  Used for FX, rays, rings, flashes."""
    m, new = _new_mat(name)
    if not new:
        return m
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1)
    em.inputs["Strength"].default_value = strength
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    if additive:
        # transparent + emission = light that adds on top of the scene
        add = nt.nodes.new("ShaderNodeAddShader")
        info = nt.nodes.new("ShaderNodeObjectInfo")
        mul = nt.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = strength
        nt.links.new(info.outputs["Alpha"], mul.inputs[0])
        nt.links.new(mul.outputs[0], em.inputs["Strength"])
        nt.links.new(tr.outputs[0], add.inputs[0])
        nt.links.new(em.outputs[0], add.inputs[1])
        nt.links.new(add.outputs[0], out.inputs["Surface"])
    else:
        info = nt.nodes.new("ShaderNodeObjectInfo")
        nt.links.new(info.outputs["Alpha"], mix.inputs[0])
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
    m.diffuse_color = (*color, 1)
    return m


def mat_beam(name, color, strength=4.0):
    """Light-ray cone: glow fades along the object's local Z (generated
    coords) and toward the edges -> soft volumetric-looking beam."""
    m, new = _new_mat(name)
    if not new:
        return m
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")       # fade along length
    ramp.color_ramp.elements[0].position = 0.0      # bright at the source
    ramp.color_ramp.elements[0].color = (1, 1, 1, 1)
    ramp.color_ramp.elements[1].position = 1.0      # dark at the far end
    ramp.color_ramp.elements[1].color = (0, 0, 0, 1)
    nt.links.new(sep.outputs["Z"], ramp.inputs[0])
    lw = nt.nodes.new("ShaderNodeLayerWeight")       # soft edges
    lw.inputs["Blend"].default_value = 0.35
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    nt.links.new(lw.outputs["Facing"], inv.inputs[1])
    edge = nt.nodes.new("ShaderNodeMath")
    edge.operation = "POWER"
    edge.inputs[1].default_value = 3.0
    nt.links.new(inv.outputs[0], edge.inputs[0])
    info = nt.nodes.new("ShaderNodeObjectInfo")
    m1 = nt.nodes.new("ShaderNodeMath"); m1.operation = "MULTIPLY"
    m2 = nt.nodes.new("ShaderNodeMath"); m2.operation = "MULTIPLY"
    m3 = nt.nodes.new("ShaderNodeMath"); m3.operation = "MULTIPLY"
    m3.inputs[1].default_value = strength
    nt.links.new(ramp.outputs["Color"], m1.inputs[0])
    nt.links.new(edge.outputs[0], m1.inputs[1])
    nt.links.new(m1.outputs[0], m2.inputs[0])
    nt.links.new(info.outputs["Alpha"], m2.inputs[1])
    nt.links.new(m2.outputs[0], m3.inputs[0])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1)
    nt.links.new(m3.outputs[0], em.inputs["Strength"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(tr.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs["Surface"])
    return m


def mat_image(name, img_path, rough=0.3, metal=0.0, emit=0.0, alpha=False,
              bump=0.0, tint=None, fade=False):
    """Material driven by an image texture (logos, emblems, coins)."""
    m, new = _new_mat(name)
    if not new:
        return m
    nt = m.node_tree
    b = pbsdf(m)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(img_path, check_existing=True)
    tex.extension = "CLIP"
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit > 0:
        nt.links.new(tex.outputs["Color"], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = emit
    if alpha or fade:
        a_src = tex.outputs["Alpha"]
        if fade:
            info = nt.nodes.new("ShaderNodeObjectInfo")
            mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
            nt.links.new(tex.outputs["Alpha"], mul.inputs[0])
            nt.links.new(info.outputs["Alpha"], mul.inputs[1])
            a_src = mul.outputs[0]
        nt.links.new(a_src, b.inputs["Alpha"])
        try:
            m.surface_render_method = "BLENDED"
        except Exception:
            pass
    if bump > 0:
        bp = nt.nodes.new("ShaderNodeBump")
        bp.inputs["Strength"].default_value = bump
        bw = nt.nodes.new("ShaderNodeRGBToBW")
        nt.links.new(tex.outputs["Color"], bw.inputs[0])
        nt.links.new(bw.outputs[0], bp.inputs["Height"])
        nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    return m


def mat_text(name, top, bottom, strength=2.2, outline=False):
    """Title text: vertical color gradient (object-space Z) + glow, with
    opacity from Object Info > Alpha so texts can fade."""
    m, new = _new_mat(name)
    if not new:
        return m
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    info = nt.nodes.new("ShaderNodeObjectInfo")
    em = nt.nodes.new("ShaderNodeEmission")
    if outline:
        em.inputs["Color"].default_value = (*top, 1)
        em.inputs["Strength"].default_value = strength
    else:
        tc = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(tc.outputs["Generated"], sep.inputs[0])
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.05
        ramp.color_ramp.elements[0].color = (*bottom, 1)
        ramp.color_ramp.elements[1].position = 0.85
        ramp.color_ramp.elements[1].color = (*top, 1)
        nt.links.new(sep.outputs["Y"], ramp.inputs[0])
        nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
        em.inputs["Strength"].default_value = strength
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(info.outputs["Alpha"], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return m


def add_bevel(ob, width=0.02, segments=2):
    m = ob.modifiers.new("Bevel", "BEVEL")
    m.width = width
    m.segments = segments
    m.limit_method = "ANGLE"
    return m


def add_subsurf(ob, levels=1):
    m = ob.modifiers.new("Sub", "SUBSURF")
    m.levels = levels
    m.render_levels = levels
    return m


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_v(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))
