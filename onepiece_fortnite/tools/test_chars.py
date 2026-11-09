"""Quick lineup render of all characters (debug helper)."""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
import config as C
from op_lib import characters as CH, utils as U
pose = sys.argv[-1] if len(sys.argv) > 1 and not sys.argv[-1].endswith('.py') else None
sc = bpy.context.scene
chars = []
for i, b in enumerate(["build_luffy", "build_zoro", "build_nami", "build_sanji", "build_chopper"]):
    ch = CH.BUILDERS[b](loc=((i - 2) * 1.3, 0, 0))
    chars.append(ch)
    if pose == "action":
        CH.key_pose(ch, 1, ["luffy_fist_up", "zoro_stance", "nami_pose", "sanji_kick", "chopper_jump"][i])
    else:
        CH.key_pose(ch, 1, "rest")
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam)
cam.location = (0, 7.5, 1.4); cam.rotation_euler = (math.radians(88), 0, math.radians(180))
cam.data.lens = 40
sc.camera = cam
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.4, 0.5, 0.7, 1)
l = bpy.data.objects.new("S", bpy.data.lights.new("S", "SUN")); sc.collection.objects.link(l)
l.rotation_euler = (math.radians(50), 0, math.radians(150)); l.data.energy = 4
fl = bpy.data.objects.new("F", U.mesh_plane("F", 30, 30)); sc.collection.objects.link(fl)
sc.render.engine = "CYCLES"; sc.cycles.samples = 16
sc.render.resolution_x, sc.render.resolution_y = 1200, 600
sc.render.filepath = sys.argv[-2] if len(sys.argv) > 2 else "/tmp/chars.png"
bpy.ops.render.render(write_still=True)
