from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    StringProperty,
)


RESOLUTION_ITEMS = (
    ("512", "512", "512 x 512"),
    ("1024", "1024", "1024 x 1024"),
    ("2048", "2048", "2048 x 2048"),
    ("4096", "4096", "4096 x 4096"),
    ("8192", "8192", "8192 x 8192"),
)


class ARB_PG_Settings(bpy.types.PropertyGroup):
    input_mode: EnumProperty(
        name="Input Mode",
        items=(
            ("GLB_FILE", "GLB File", "Process one GLB file"),
            (
                "SELECTED_OBJECTS",
                "Selected Objects",
                "Process selected Mesh objects independently",
            ),
        ),
        default="GLB_FILE",
    )
    glb_path: StringProperty(
        name="GLB File",
        description="Path selected by the GLB file browser",
        default="",
    )
    target_quads: IntProperty(name="Target Quads", default=20000, min=1)
    map_resolution: EnumProperty(
        name="Map Resolution",
        items=RESOLUTION_ITEMS,
        default="2048",
    )
    merge_distance: FloatProperty(
        name="Merge Distance",
        default=0.0001,
        min=0.0,
        precision=6,
    )
    smart_uv_island_margin: FloatProperty(
        name="Smart UV Island Margin",
        default=0.02,
        min=0.0,
        max=1.0,
        precision=4,
    )
    projection_mode: EnumProperty(
        name="Projection Mode",
        items=(
            ("AUTO", "Auto", "Use Bounding Box based cage extrusion"),
            ("MANUAL", "Manual", "Set ray distance and cage extrusion"),
        ),
        default="AUTO",
    )
    auto_projection_ratio: FloatProperty(
        name="Auto Projection Ratio",
        description="Bounding Box diagonal multiplier for cage extrusion",
        default=0.005,
        min=0.0,
        precision=5,
    )
    manual_ray_distance: FloatProperty(
        name="Ray Distance",
        default=0.0,
        min=0.0,
        precision=5,
    )
    manual_cage_extrusion: FloatProperty(
        name="Cage Extrusion",
        default=0.01,
        min=0.0,
        precision=5,
    )
    diffuse_bake: BoolProperty(name="Diffuse Bake", default=True)
    normal_bake: BoolProperty(name="Normal Bake", default=True)
    continue_on_error: BoolProperty(
        name="Continue on Object Error",
        default=True,
        description="Continue Batch processing after a recoverable object error",
    )
    output_directory: StringProperty(
        name="Output Directory",
        subtype="DIR_PATH",
        default="//AutoRetopoBake_Output",
    )
    last_auto_ray_distance: FloatProperty(
        name="Auto Ray Distance",
        default=0.0,
        options={"SKIP_SAVE"},
    )
    last_auto_cage_extrusion: FloatProperty(
        name="Auto Cage Extrusion",
        default=0.0,
        options={"SKIP_SAVE"},
    )
    status_message: StringProperty(default="Ready", options={"SKIP_SAVE"})
    last_summary: StringProperty(default="", options={"SKIP_SAVE"})
    is_running: BoolProperty(default=False, options={"SKIP_SAVE"})
    current_stage: StringProperty(default="", options={"SKIP_SAVE"})
    current_stage_index: IntProperty(default=0, min=0, options={"SKIP_SAVE"})
    total_stages: IntProperty(default=9, min=1, options={"SKIP_SAVE"})
    current_object_name: StringProperty(default="", options={"SKIP_SAVE"})
    current_object_index: IntProperty(default=0, min=0, options={"SKIP_SAVE"})
    total_objects: IntProperty(default=0, min=0, options={"SKIP_SAVE"})
    start_time: FloatProperty(default=0.0, options={"SKIP_SAVE"})
    elapsed_seconds: FloatProperty(default=0.0, min=0.0, options={"SKIP_SAVE"})


CLASSES = (ARB_PG_Settings,)
