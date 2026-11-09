"""A/B color-management test on one frame (debug helper)."""
import sys, os
sys.argv = [sys.argv[0], "--quality", "preview", "--no-save"]
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import build_scene as B, bpy
B.build()
sc = bpy.context.scene
out = "/tmp/claude-0/-home-user-artur/2e7c85db-80c0-59ce-9901-bb9277434b07/scratchpad/"
for f in (230, 445):
    sc.frame_set(f)
    for name, vt, look, glare in (("agx", "AgX", "AgX - Punchy", True), ("std", "Standard", "None", True),
                                  ("agx_noglare", "AgX", "AgX - Punchy", False)):
        sc.view_settings.view_transform = vt
        sc.view_settings.look = look
        sc.render.compositor_device = "CPU" if hasattr(sc.render, "compositor_device") else None
        if hasattr(sc, "compositing_node_group"):
            sc.render.use_compositing = glare
        sc.render.filepath = out + f"ab_{f}_{name}.png"
        bpy.ops.render.render(write_still=True)
