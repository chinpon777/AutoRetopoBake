from __future__ import annotations

from pathlib import Path
import time
import traceback

import bpy
from bpy.props import StringProperty
from bpy_extras.io_utils import ImportHelper

from . import pipeline
from .utils import (
    FatalPipelineError,
    PipelineError,
    log,
    redraw_progress,
    runtime_elapsed,
    safe_object_mode,
    select_only,
)


def addon_preferences(context):
    entry = context.preferences.addons.get(__package__)
    if entry is None:
        raise PipelineError("Auto Retopo Bake preferences are unavailable")
    return entry.preferences


def begin_run(context, settings, total_objects: int = 0) -> None:
    settings.is_running = True
    settings.current_stage = ""
    settings.current_stage_index = 0
    settings.total_stages = 9
    settings.current_object_name = ""
    settings.current_object_index = 0
    settings.total_objects = total_objects
    settings.start_time = time.monotonic()
    settings.elapsed_seconds = 0.0
    settings.status_message = "Running"
    settings.last_summary = ""
    redraw_progress(context)


def set_current_object(context, settings, index: int, total: int, name: str) -> None:
    settings.current_object_index = index
    settings.total_objects = total
    settings.current_object_name = name
    settings.current_stage = ""
    settings.current_stage_index = 0
    settings.elapsed_seconds = runtime_elapsed(settings)
    settings.status_message = f"Processing {index}/{total}: {name}"
    context.window_manager.progress_update((index - 1) * settings.total_stages)
    redraw_progress(context)


def finish_run(context, settings, message: str) -> None:
    if settings.start_time > 0.0:
        settings.elapsed_seconds = max(0.0, time.monotonic() - settings.start_time)
    settings.is_running = False
    settings.status_message = message
    redraw_progress(context)


def update_progress(context, settings, current: int, total: int, label: str) -> None:
    text = f"[{current}/{total}] {label}"
    settings.current_stage_index = current
    settings.total_stages = total
    settings.current_stage = label
    settings.elapsed_seconds = runtime_elapsed(settings)
    settings.status_message = "Running"
    if settings.total_objects > 0 and settings.current_object_index > 0:
        overall = (settings.current_object_index - 1) * total + current
        status_text = (
            f"Object {settings.current_object_index}/{settings.total_objects} "
            f"{settings.current_object_name} - {text}"
        )
    else:
        overall = current
        status_text = text
    context.window_manager.progress_update(overall)
    workspace = getattr(context, "workspace", None)
    if workspace is not None and hasattr(workspace, "status_text_set"):
        workspace.status_text_set(status_text)
    log(text)
    redraw_progress(context)


class ARB_OT_SelectGLB(bpy.types.Operator, ImportHelper):
    bl_idname = "auto_retopo_bake.select_glb"
    bl_label = "Select GLB"
    bl_description = "Select a .glb file"

    filename_ext = ".glb"
    filter_glob: StringProperty(default="*.glb", options={"HIDDEN"})

    def execute(self, context):
        context.scene.auto_retopo_bake.glb_path = self.filepath
        return {"FINISHED"}


class ARB_OT_RunGLB(bpy.types.Operator):
    bl_idname = "auto_retopo_bake.run_glb"
    bl_label = "Run Auto Retopo & Bake"
    bl_options = {"REGISTER"}

    def execute(self, context):
        settings = context.scene.auto_retopo_bake
        preferences = addon_preferences(context)
        options = pipeline.options_from_properties(settings)
        path = Path(bpy.path.abspath(settings.glb_path)).expanduser().resolve()
        context.window_manager.progress_begin(0, 9)
        begin_run(context, settings)
        try:
            result = pipeline.run_glb_file(
                path,
                options,
                preferences,
                lambda current, total, label: update_progress(
                    context, settings, current, total, label
                ),
            )
            settings.last_auto_ray_distance = result.ray_distance
            settings.last_auto_cage_extrusion = result.cage_extrusion
            settings.last_summary = f"{path.name}: SUCCESS"
            finish_run(context, settings, "Completed")
            self.report({"INFO"}, f"Completed: {result.low.name}")
            return {"FINISHED"}
        except PipelineError as exc:
            settings.last_summary = f"{path.name}: FAILED - {exc}"
            finish_run(context, settings, f"Failed: {exc}")
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        except Exception as exc:
            traceback.print_exc()
            finish_run(context, settings, f"Fatal error: {exc}")
            self.report({"ERROR"}, f"Fatal error: {exc}")
            return {"CANCELLED"}
        finally:
            if settings.is_running:
                finish_run(context, settings, settings.status_message)
            safe_object_mode()
            context.window_manager.progress_end()
            workspace = getattr(context, "workspace", None)
            if workspace is not None and hasattr(workspace, "status_text_set"):
                workspace.status_text_set(None)


class ARB_OT_RunSelectedBatch(bpy.types.Operator):
    bl_idname = "auto_retopo_bake.run_selected_batch"
    bl_label = "Run Selected Objects Batch"
    bl_options = {"REGISTER"}

    def execute(self, context):
        settings = context.scene.auto_retopo_bake
        preferences = addon_preferences(context)
        options = pipeline.options_from_properties(settings)
        sources = sorted(
            (
                obj
                for obj in context.scene.objects
                if obj.select_get() and obj.type == "MESH"
            ),
            key=lambda obj: obj.name.casefold(),
        )
        if not sources:
            self.report({"ERROR"}, "No selected Mesh objects")
            return {"CANCELLED"}

        successes = []
        failures = []
        records = []
        fatal = False
        total = len(sources)
        context.window_manager.progress_begin(0, total * 9)
        begin_run(context, settings, total_objects=total)
        try:
            for index, source in enumerate(sources, start=1):
                message = f"Processing {index} / {total} : {source.name}"
                set_current_object(context, settings, index, total, source.name)
                workspace = getattr(context, "workspace", None)
                if workspace is not None and hasattr(workspace, "status_text_set"):
                    workspace.status_text_set(message)
                log(message)
                try:
                    result = pipeline.run_selected_object(
                        source,
                        options,
                        preferences,
                        lambda current, stage_total, label: update_progress(
                            context, settings, current, stage_total, label
                        ),
                    )
                    successes.append((source.name, result))
                    records.append((source.name, True, ""))
                    settings.last_auto_ray_distance = result.ray_distance
                    settings.last_auto_cage_extrusion = result.cage_extrusion
                    log(f"{source.name} : SUCCESS")
                except PipelineError as exc:
                    safe_object_mode()
                    failures.append((source.name, str(exc)))
                    records.append((source.name, False, str(exc)))
                    log(f"{source.name} : FAILED - {exc}")
                    if isinstance(exc, FatalPipelineError) or not settings.continue_on_error:
                        fatal = True
                        break
                except Exception as exc:
                    traceback.print_exc()
                    safe_object_mode()
                    failures.append((source.name, f"Fatal error: {exc}"))
                    records.append((source.name, False, f"Fatal error: {exc}"))
                    fatal = True
                    break

            if successes:
                try:
                    pipeline.save_batch_blend(options)
                except Exception as exc:
                    traceback.print_exc()
                    failures.append(("BLEND save", str(exc)))
                    records.append(("BLEND save", False, str(exc)))
                    fatal = True
                low_objects = [result.low for _name, result in successes]
                select_only(low_objects, low_objects[-1])

            summary_lines = ["=== Auto Retopo Bake Summary ===", ""]
            for name, succeeded, error in records:
                summary_lines.append(
                    f"{name} : SUCCESS" if succeeded else f"{name} : FAILED - {error}"
                )
            summary_lines.extend(
                ["", f"{len(successes)} succeeded", f"{len(failures)} failed"]
            )
            if fatal:
                summary_lines.append("Batch stopped for safety")
            settings.last_summary = "\n".join(summary_lines)
            log(settings.last_summary)
            level = {"WARNING"} if failures else {"INFO"}
            if failures:
                completion = (
                    f"Completed: {len(successes)} succeeded / "
                    f"{len(failures)} failed"
                )
            else:
                completion = f"Completed: {len(successes)}/{total} objects"
            finish_run(context, settings, completion)
            self.report(level, completion)
            return {"FINISHED"} if successes else {"CANCELLED"}
        finally:
            if settings.is_running:
                finish_run(context, settings, settings.status_message)
            safe_object_mode()
            context.window_manager.progress_end()
            workspace = getattr(context, "workspace", None)
            if workspace is not None and hasattr(workspace, "status_text_set"):
                workspace.status_text_set(None)


CLASSES = (ARB_OT_SelectGLB, ARB_OT_RunGLB, ARB_OT_RunSelectedBatch)
