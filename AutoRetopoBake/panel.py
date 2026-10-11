from __future__ import annotations

import bpy

from .utils import format_elapsed, runtime_elapsed


class ARB_PT_MainPanel(bpy.types.Panel):
    bl_label = "Auto Retopo Bake"
    bl_idname = "ARB_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Auto Retopo Bake"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.auto_retopo_bake

        layout.prop(settings, "input_mode", expand=True)
        if settings.input_mode == "GLB_FILE":
            row = layout.row(align=True)
            row.prop(settings, "glb_path", text="")
            row.operator("auto_retopo_bake.select_glb", text="", icon="FILE_FOLDER")
        else:
            selected_meshes = sum(
                1 for obj in context.selected_objects if obj.type == "MESH"
            )
            layout.label(text=f"Selected Meshes: {selected_meshes}")
            layout.prop(settings, "continue_on_error")

        layout.separator()
        layout.prop(settings, "target_quads")
        layout.prop(settings, "map_resolution")
        layout.prop(settings, "merge_distance")
        layout.prop(settings, "smart_uv_island_margin")

        box = layout.box()
        box.prop(settings, "projection_mode", expand=True)
        if settings.projection_mode == "AUTO":
            box.prop(settings, "auto_projection_ratio")
            row = box.row()
            row.enabled = False
            row.prop(settings, "last_auto_ray_distance")
            row = box.row()
            row.enabled = False
            row.prop(settings, "last_auto_cage_extrusion")
        else:
            box.prop(settings, "manual_ray_distance")
            box.prop(settings, "manual_cage_extrusion")

        row = layout.row(align=True)
        row.prop(settings, "diffuse_bake")
        row.prop(settings, "normal_bake")
        layout.prop(settings, "output_directory")

        layout.separator()
        run_row = layout.row()
        run_row.enabled = not settings.is_running
        if settings.input_mode == "GLB_FILE":
            run_row.operator("auto_retopo_bake.run_glb", icon="PLAY")
        else:
            run_row.operator("auto_retopo_bake.run_selected_batch", icon="PLAY")

        status_box = layout.box()
        if not settings.is_running and settings.current_stage_index == 0:
            status_box.label(text="Ready", icon="INFO")
        else:
            if settings.total_objects > 0 and settings.current_object_index > 0:
                status_box.label(
                    text=(
                        f"Object: {settings.current_object_index}/"
                        f"{settings.total_objects} {settings.current_object_name}"
                    )
                )
            if settings.current_stage_index > 0:
                status_box.label(
                    text=(
                        f"Progress: {settings.current_stage_index}/"
                        f"{settings.total_stages} {settings.current_stage}"
                    )
                )
            else:
                status_box.label(text="Progress: Starting")
            status_box.label(
                text=f"Elapsed: {format_elapsed(runtime_elapsed(settings))}"
            )
            status_box.label(text=settings.status_message, icon="INFO")
        if settings.last_summary:
            box = layout.box()
            for line in settings.last_summary.splitlines():
                box.label(text=line or " ")


CLASSES = (ARB_PT_MainPanel,)
