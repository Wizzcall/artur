"""
On-screen titles and full-screen flashes.

Titles are real 3D text objects (extruded + beveled, glowing gradient,
dark outline) parented to the camera at HUD_DIST, so they always sit in
screen space.  Positions use normalized screen coordinates:
    y = +1 top edge, 0 center, -1 bottom edge;  width = fraction of frame.
NOTE: keep the camera lens at HUD_LENS while titles are on screen.
"""
import os
import bpy
from mathutils import Vector

import config as C
from .utils import (key, key_alpha, key_scale, key_loc, mat_text, mat_emit_fade, obj_from_mesh,
                    mesh_plane, only_camera_visible, link)

HUD_DIST = 0.6        # meters in front of the camera
HUD_LENS = 30.0       # mm (vertical sensor fit, sensor 36 mm)
SENSOR = 36.0


def half_height():
    return HUD_DIST * (SENSOR / 2) / HUD_LENS


def half_width():
    return half_height() * C.WIDTH / C.HEIGHT


def _font(italic=False):
    for p in (C.FONT_ITALIC_CANDIDATES if italic else C.FONT_CANDIDATES):
        if os.path.exists(p):
            return bpy.data.fonts.load(p, check_existing=True)
    return None


def _text_obj(name, body, mat, size, extrude, bevel, offset=0.0, italic=False, spacing=1.0):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    f = _font(italic)
    if f:
        cu.font = f
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.size = size
    cu.extrude = extrude
    cu.bevel_depth = bevel
    cu.bevel_resolution = 2
    cu.offset = offset
    cu.space_line = 0.85
    cu.space_character = spacing
    cu.materials.append(mat)
    ob = bpy.data.objects.new(name, cu)
    link(ob)
    only_camera_visible(ob)
    return ob


def title(name, body, cam, f_in, f_out, y=0.5, width=0.86, style="gold", italic=True,
          anim="slam", max_height=0.22):
    """Create a screen-space title.  Returns the parent empty.
    style: 'gold' | 'white' | 'red' | 'blue'   anim: 'slam' | 'rise' | 'pop'."""
    styles = {
        "gold": (C.COLORS["text_top"], C.COLORS["text_bottom"]),
        "white": ((1, 1, 1), (0.75, 0.85, 1.0)),
        "red": ((1.0, 0.45, 0.3), (0.85, 0.02, 0.02)),
        "blue": ((0.55, 0.85, 1.0), (0.25, 0.25, 1.0)),
        "green": ((0.6, 1.0, 0.5), (0.05, 0.55, 0.15)),
        "pink": ((1.0, 0.75, 0.9), (1.0, 0.25, 0.55)),
    }
    top, bot = styles.get(style, styles["gold"])
    m_face = mat_text(f"TXT_{style}", top, bot, 2.4)
    m_out = mat_text("TXT_outline", C.COLORS["text_outline"], C.COLORS["text_outline"], 1.0, outline=True)

    root = bpy.data.objects.new(name, None)
    link(root)
    root.parent = cam
    root.location = (0, y * half_height(), -HUD_DIST)
    size = 0.1
    face = _text_obj(f"{name}_face", body, m_face, size, 0.012, 0.004, 0.0, italic)
    face.parent = root
    out = _text_obj(f"{name}_outline", body, m_out, size, 0.006, 0.0065, 0.0, italic)
    out.parent = root
    out.location = (0.003, -0.004, -0.014)
    # auto-fit to the requested width / height
    bpy.context.view_layer.update()
    dims = face.dimensions
    sc = min(width * 2 * half_width() / max(dims.x, 1e-4), max_height * 2 * half_height() / max(dims.y, 1e-4))
    s_final = Vector((sc, sc, sc))
    for o in (face, out):
        o.color = (1, 1, 1, 0)
        key_alpha(o, f_in - 1, 0.0, "CONSTANT")
        key_alpha(o, f_in, 1.0, "CONSTANT")
        key_alpha(o, f_out - 6, 1.0, "LINEAR")
        key_alpha(o, f_out, 0.0, "LINEAR")
    base = root.location.copy()
    if anim == "slam":            # big -> normal with overshoot
        key_scale(root, f_in, s_final * 2.4, "BACK")
        key_scale(root, f_in + 7, s_final, "LINEAR")
        key_scale(root, f_out - 6, s_final * 1.06, "LINEAR")
        key_scale(root, f_out, s_final * 1.25, "LINEAR")
    elif anim == "rise":
        key_scale(root, f_in, s_final * 0.9, "BEZIER")
        key_scale(root, f_out, s_final * 1.05, "LINEAR")
        key_loc(root, f_in, base - Vector((0, 0.05 * half_height(), 0)), "BACK")
        key_loc(root, f_in + 10, base, "BEZIER")
    else:                         # pop
        key_scale(root, f_in, s_final * 0.01, "BACK")
        key_scale(root, f_in + 8, s_final, "LINEAR")
        key_scale(root, f_out - 4, s_final * 1.04, "LINEAR")
        key_scale(root, f_out, s_final * 0.01, "LINEAR")
    for o in (root, face, out):
        key(o, "hide_render", 1, True, "CONSTANT")
        key(o, "hide_render", f_in, False, "CONSTANT")
        key(o, "hide_render", f_out + 1, True, "CONSTANT")
    return root


def overlay(name, cam, color, additive=True, dist=None):
    """Full-screen plane in front of the camera (flash / fade)."""
    dist = dist or HUD_DIST * 0.5
    mat = mat_emit_fade(f"{name}_Mat", color, 1.0 if not additive else 6.0, additive=additive)
    h = dist * (SENSOR / 2) / HUD_LENS * 1.6
    ob = obj_from_mesh(name, mesh_plane(f"{name}_mesh", h * 2, h * 2), mat, cam, (0, 0, -dist))
    only_camera_visible(ob)
    ob.color = (1, 1, 1, 0)
    key_alpha(ob, 1, 0.0, "CONSTANT")
    return ob


def flash(ob, f, peak=1.0, attack=2, release=10, hold=0):
    """Animate an overlay: 0 -> peak -> 0."""
    key_alpha(ob, f - attack - 1, 0.0, "LINEAR")
    key_alpha(ob, f, peak, "LINEAR")
    if hold:
        key_alpha(ob, f + hold, peak, "LINEAR")
    key_alpha(ob, f + hold + release, 0.0, "LINEAR")
