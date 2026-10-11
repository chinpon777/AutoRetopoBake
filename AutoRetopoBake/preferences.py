from __future__ import annotations

import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty


class ARB_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    autoremesher_path: StringProperty(
        name="AutoRemesher Executable",
        subtype="FILE_PATH",
        description="Path to AutoRemesher executable or Linux AppImage",
        default="",
    )
    appimage_extract_and_run: BoolProperty(
        name="Use APPIMAGE_EXTRACT_AND_RUN",
        description="Run AppImage without a FUSE mount",
        default=True,
    )
    xvfb_run_path: StringProperty(
        name="xvfb-run (Optional)",
        subtype="FILE_PATH",
        description="Only needed when Blender has no X/Wayland display",
        default="",
    )
    timeout_seconds: IntProperty(
        name="Timeout (seconds)",
        default=3600,
        min=1,
    )

    def draw(self, _context):
        layout = self.layout
        layout.prop(self, "autoremesher_path")
        layout.prop(self, "appimage_extract_and_run")
        layout.prop(self, "xvfb_run_path")
        layout.prop(self, "timeout_seconds")


CLASSES = (ARB_AddonPreferences,)
