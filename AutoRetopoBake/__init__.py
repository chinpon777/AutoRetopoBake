"""Auto Retopo Bake Blender add-on."""

bl_info = {
    "name": "Auto Retopo Bake",
    "author": "AutoNormalBake",
    "version": (1, 2, 0),
    "blender": (5, 2, 0),
    "location": "3D View > Sidebar > Auto Retopo Bake",
    "description": "AutoRemesher retopology with diffuse and normal baking",
    "category": "Object",
}

import bpy

from . import operators, panel, preferences, properties


CLASSES = (
    *preferences.CLASSES,
    *properties.CLASSES,
    *operators.CLASSES,
    *panel.CLASSES,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.auto_retopo_bake = bpy.props.PointerProperty(
        type=properties.ARB_PG_Settings
    )


def unregister():
    if hasattr(bpy.types.Scene, "auto_retopo_bake"):
        del bpy.types.Scene.auto_retopo_bake
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
