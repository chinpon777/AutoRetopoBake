from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    StringProperty,
)

from .preferences import DEFAULT_OUTPUT_DIRECTORY


RESOLUTION_ITEMS = (
    ("512", "512", "512 x 512"),
    ("1024", "1024", "1024 x 1024"),
    ("2048", "2048", "2048 x 2048"),
    ("4096", "4096", "4096 x 4096"),
    ("8192", "8192", "8192 x 8192"),
)


def _addon_preferences():
    context = getattr(bpy, "context", None)
    blender_preferences = getattr(context, "preferences", None)
    if blender_preferences is None:
        return None
    entry = blender_preferences.addons.get(__package__)
    return entry.preferences if entry is not None else None


def _get_output_directory(settings) -> str:
    preferences = _addon_preferences()
    legacy_value = settings.get("output_directory")
    fallback_value = settings.get("_output_directory", DEFAULT_OUTPUT_DIRECTORY)
    if preferences is None:
        return legacy_value or fallback_value

    if (
        preferences.output_directory == DEFAULT_OUTPUT_DIRECTORY
        and legacy_value
        and legacy_value != DEFAULT_OUTPUT_DIRECTORY
        and not settings.get("_output_directory_migrated", False)
    ):
        preferences.output_directory = legacy_value
        settings["_output_directory_migrated"] = True
    return preferences.output_directory


def _set_output_directory(settings, value: str) -> None:
    settings["_output_directory"] = value
    settings["_output_directory_migrated"] = True
    preferences = _addon_preferences()
    if preferences is not None and preferences.output_directory != value:
        preferences.output_directory = value


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
    target_quads: IntProperty(name="Target Quads", default=30000, min=1)
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
        description="Persistent output directory shared by all Blender files",
        subtype="DIR_PATH",
        default=DEFAULT_OUTPUT_DIRECTORY,
        get=_get_output_directory,
        set=_set_output_directory,
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
