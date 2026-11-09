"""
Environment: procedural sky (night -> sunrise blend), stars, sun glow,
animated ocean (Ocean modifier), sun / moon / fill lights.
"""
import math
import bpy
from mathutils import Vector

import config as C
from .utils import (key, key_loc, mat_basic, obj_from_mesh, mesh_plane, link,
                    mat_emit_fade, sphere, no_shadow)

# Direction the dawn sun comes from (behind-left of the ship, low)
SUN_DIR = Vector((-0.55, -0.80, 0.16)).normalized()


def build_world(day_switch_frame, day_switch_len=12):
    """World shader.  A 'DayMix' value node (0 = night, 1 = sunrise) is
    keyframed so the whole sky changes in sync with the token flash."""
    w = bpy.data.worlds.new("SkyWorld")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    N, L = nt.nodes.new, nt.links.new

    out = N("ShaderNodeOutputWorld")
    tc = N("ShaderNodeTexCoord")
    sep = N("ShaderNodeSeparateXYZ")
    L(tc.outputs["Generated"], sep.inputs[0])

    # --- Night gradient ------------------------------------------------
    night = N("ShaderNodeValToRGB")
    night.color_ramp.elements[0].position = 0.0
    night.color_ramp.elements[0].color = (*C.COLORS["night_sky_horizon"], 1)
    night.color_ramp.elements[1].position = 0.45
    night.color_ramp.elements[1].color = (*C.COLORS["night_sky_top"], 1)
    L(sep.outputs["Z"], night.inputs[0])

    # stars: high-frequency voronoi thresholded
    vor = N("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 260
    L(tc.outputs["Generated"], vor.inputs["Vector"])
    star_ramp = N("ShaderNodeValToRGB")
    star_ramp.color_ramp.elements[0].position = 0.0
    star_ramp.color_ramp.elements[0].color = (3, 3, 3.5, 1)
    star_ramp.color_ramp.elements[1].position = 0.045
    star_ramp.color_ramp.elements[1].color = (0, 0, 0, 1)
    L(vor.outputs["Distance"], star_ramp.inputs[0])
    above = N("ShaderNodeMath"); above.operation = "GREATER_THAN"
    above.inputs[1].default_value = 0.04
    L(sep.outputs["Z"], above.inputs[0])
    star_mask = N("ShaderNodeMixRGB"); star_mask.blend_type = "MULTIPLY"
    star_mask.inputs[0].default_value = 1.0
    L(star_ramp.outputs["Color"], star_mask.inputs[1])
    L(above.outputs[0], star_mask.inputs[2])
    night_add = N("ShaderNodeMixRGB"); night_add.blend_type = "ADD"
    night_add.inputs[0].default_value = 1.0
    L(night.outputs["Color"], night_add.inputs[1])
    L(star_mask.outputs["Color"], night_add.inputs[2])

    # --- Sunrise gradient + sun glow ------------------------------------
    day = N("ShaderNodeValToRGB")
    cr = day.color_ramp
    cr.elements[0].position = 0.0
    cr.elements[0].color = (*C.COLORS["dawn_sky_horizon"], 1)
    cr.elements[1].position = 0.55
    cr.elements[1].color = (*C.COLORS["dawn_sky_top"], 1)
    e = cr.elements.new(0.12)
    e.color = (0.95, 0.45, 0.45, 1)
    L(sep.outputs["Z"], day.inputs[0])

    dot = N("ShaderNodeVectorMath"); dot.operation = "DOT_PRODUCT"
    dot.inputs[1].default_value = SUN_DIR
    L(tc.outputs["Generated"], dot.inputs[0])
    clampn = N("ShaderNodeMath"); clampn.operation = "MAXIMUM"
    clampn.inputs[1].default_value = 0.0
    L(dot.outputs["Value"], clampn.inputs[0])
    glow = N("ShaderNodeMath"); glow.operation = "POWER"
    glow.inputs[1].default_value = 18.0
    L(clampn.outputs[0], glow.inputs[0])
    disk = N("ShaderNodeMath"); disk.operation = "POWER"
    disk.inputs[1].default_value = 1800.0
    L(clampn.outputs[0], disk.inputs[0])
    sun_amt = N("ShaderNodeMath"); sun_amt.operation = "MULTIPLY_ADD"
    sun_amt.inputs[1].default_value = 25.0
    L(disk.outputs[0], sun_amt.inputs[0])
    L(glow.outputs[0], sun_amt.inputs[2])
    sun_col = N("ShaderNodeMixRGB"); sun_col.blend_type = "ADD"
    L(sun_amt.outputs[0], sun_col.inputs[0])
    L(day.outputs["Color"], sun_col.inputs[1])
    sun_col.inputs[2].default_value = (1.0, 0.75, 0.4, 1)

    # below horizon: darker ocean-ish haze (seen through wave gaps)
    # --- Final mix ------------------------------------------------------
    daymix = N("ShaderNodeValue"); daymix.name = "DayMix"; daymix.label = "DayMix"
    mix = N("ShaderNodeMixRGB")
    L(daymix.outputs[0], mix.inputs[0])
    L(night_add.outputs["Color"], mix.inputs[1])
    L(sun_col.outputs["Color"], mix.inputs[2])
    bg = N("ShaderNodeBackground")
    L(mix.outputs["Color"], bg.inputs["Color"])
    strength = N("ShaderNodeMath"); strength.operation = "MULTIPLY_ADD"
    L(daymix.outputs[0], strength.inputs[0])
    strength.inputs[1].default_value = 0.45     # day adds +0.45
    strength.inputs[2].default_value = 0.55     # night base
    L(strength.outputs[0], bg.inputs["Strength"])
    L(bg.outputs[0], out.inputs["Surface"])

    sock = daymix.outputs[0]
    sock.default_value = 0.0
    sock.keyframe_insert("default_value", frame=day_switch_frame)
    sock.default_value = 1.0
    sock.keyframe_insert("default_value", frame=day_switch_frame + day_switch_len)
    return w


def build_ocean(end_frame):
    """Big animated ocean.  The ocean drifts backwards (-Y) so the ship
    seems to sail forward while staying at the origin."""
    me = mesh_plane("OceanBase", 2, 2)
    ocean = obj_from_mesh("Ocean", me)
    mod = ocean.modifiers.new("Ocean", "OCEAN")
    mod.geometry_mode = "GENERATE"
    mod.resolution = C.OCEAN_RESOLUTION
    mod.spatial_size = 60
    mod.repeat_x = 5
    mod.repeat_y = 5
    mod.wave_scale = 0.9
    mod.choppiness = 1.1
    mod.wind_velocity = 14
    mod.wave_alignment = 0.4
    mod.wave_direction = math.radians(90)
    mod.random_seed = C.SEED
    try:
        mod.use_normals = True
    except Exception:
        pass
    mod.time = 1.0
    mod.keyframe_insert("time", frame=1)
    mod.time = 1.0 + end_frame / C.FPS * 0.8
    C_ = bpy.context.preferences.edit
    C_.keyframe_new_interpolation_type = "LINEAR"
    mod.keyframe_insert("time", frame=end_frame)
    C_.keyframe_new_interpolation_type = "BEZIER"
    for p in ocean.data.polygons:
        p.use_smooth = True
    ocean.location = (-150, -150, 0)      # 300 m square centered on origin
    # sailing drift
    key_loc(ocean, 1, (-150, -150, 0), "LINEAR")
    key_loc(ocean, end_frame, (-150, -150 - end_frame / C.FPS * 1.6, 0), "LINEAR")

    # Water material: deep blue, glossy, a bit of subsurface-ish glow at crests
    m = bpy.data.materials.new("Water")
    m.use_nodes = True
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Roughness"].default_value = 0.06
    b.inputs["Specular IOR Level"].default_value = 0.8
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sepz = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sepz.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.004, 0.03, 0.08, 1)
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = (0.02, 0.28, 0.42, 1)
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -0.6
    mr.inputs["From Max"].default_value = 1.2
    nt.links.new(sepz.outputs["Z"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], ramp.inputs[0])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    m.diffuse_color = (0.02, 0.15, 0.3, 1)
    ocean.data.materials.append(m)
    ocean.visible_shadow = False      # cheaper, and keeps the hull bright
    return ocean


def build_lights(day_switch_frame, day_switch_len=12):
    """Sun (moon at night -> warm sunrise), plus a front fill and a rim."""
    f0, f1 = day_switch_frame, day_switch_frame + day_switch_len

    sun_data = bpy.data.lights.new("Sun", "SUN")
    sun = bpy.data.objects.new("Sun", sun_data)
    link(sun)
    sun_data.angle = math.radians(3)
    # rotation so the light travels opposite SUN_DIR
    sun.rotation_euler = (-SUN_DIR).to_track_quat("-Z", "Y").to_euler()
    for f, col, en in ((f0, (0.45, 0.6, 1.0), 0.6), (f1, (1.0, 0.72, 0.45), 4.2)):
        sun_data.color = col
        sun_data.energy = en
        sun_data.keyframe_insert("color", frame=f)
        sun_data.keyframe_insert("energy", frame=f)

    # front key (warm), no shadows: makes the faces readable
    fill_d = bpy.data.lights.new("FrontFill", "SUN")
    fill = bpy.data.objects.new("FrontFill", fill_d)
    link(fill)
    fill_d.angle = math.radians(20)
    try:
        fill_d.use_shadow = False
    except Exception:
        pass
    fill.rotation_euler = Vector((0.35, 1.0, 0.75)).normalized().to_track_quat("Z", "Y").to_euler()
    for f, col, en in ((f0, (0.4, 0.5, 1.0), 0.15), (f1, (1.0, 0.9, 0.8), 2.4)):
        fill_d.color = col
        fill_d.energy = en
        fill_d.keyframe_insert("color", frame=f)
        fill_d.keyframe_insert("energy", frame=f)

    # cool rim from the opposite side for the "trailer" edge light
    rim_d = bpy.data.lights.new("Rim", "SUN")
    rim = bpy.data.objects.new("Rim", rim_d)
    link(rim)
    try:
        rim_d.use_shadow = False
    except Exception:
        pass
    rim.rotation_euler = Vector((0.9, -0.6, 0.35)).normalized().to_track_quat("Z", "Y").to_euler()
    for f, en in ((f0, 0.3), (f1, 1.2)):
        rim_d.color = (0.55, 0.75, 1.0)
        rim_d.energy = en
        rim_d.keyframe_insert("energy", frame=f)

    # moon (night only) - an emissive sphere far away
    moon_mat = mat_emit_fade("MoonMat", (0.85, 0.9, 1.0), 6.0)
    moon = sphere("Moon", 6.0, moon_mat, loc=(-60, 180, 70))
    no_shadow(moon)
    moon.color = (1, 1, 1, 1)
    key(moon, "color", f0, (1, 1, 1, 1), index=-1)
    key(moon, "color", f1, (1, 1, 1, 0), index=-1)
    return sun, fill, rim
