from __future__ import annotations

import math
from pathlib import Path
import re
import time
from typing import Iterable

import bpy
from mathutils import Matrix, Vector


class PipelineError(RuntimeError):
    pass


class FatalPipelineError(PipelineError):
    pass


def log(message: str) -> None:
    print(f"[Auto Retopo Bake] {message}", flush=True)


def runtime_elapsed(settings) -> float:
    if settings.is_running and settings.start_time > 0.0:
        return max(0.0, time.monotonic() - settings.start_time)
    return max(0.0, float(settings.elapsed_seconds))


def format_elapsed(seconds: float) -> str:
    minutes, remaining = divmod(int(max(0.0, seconds)), 60)
    return f"{minutes:02d}:{remaining:02d}"


def redraw_progress(context) -> None:
    window_manager = getattr(context, "window_manager", None)
    if window_manager is None:
        return
    for window in window_manager.windows:
        screen = getattr(window, "screen", None)
        if screen is None:
            continue
        for area in screen.areas:
            area.tag_redraw()
    if not bpy.app.background:
        try:
            bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
        except (RuntimeError, AttributeError):
            pass


def safe_object_mode() -> None:
    obj = bpy.context.object
    if obj is not None and obj.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def select_only(objects: Iterable[bpy.types.Object], active: bpy.types.Object) -> None:
    safe_object_mode()
    for obj in bpy.context.view_layer.objects:
        obj.select_set(False)
    for obj in objects:
        obj.hide_set(False)
        obj.hide_viewport = False
        obj.select_set(True)
    bpy.context.view_layer.objects.active = active


def bake_object_to_world_space(obj: bpy.types.Object) -> None:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    world_matrix = evaluated.matrix_world.copy()
    mesh = bpy.data.meshes.new_from_object(
        evaluated, preserve_all_data_layers=True, depsgraph=depsgraph
    )
    if mesh is None:
        raise PipelineError(f"Could not evaluate mesh: {obj.name}")
    mesh.transform(world_matrix, shape_keys=True)
    if world_matrix.to_3x3().determinant() < 0:
        mesh.flip_normals()
    obj.data = mesh
    obj.modifiers.clear()
    obj.parent = None
    obj.matrix_world = Matrix.Identity(4)


def join_meshes_world_space(
    mesh_objects: list[bpy.types.Object], object_name: str
) -> bpy.types.Object:
    if not mesh_objects:
        raise PipelineError("No Mesh objects to join")
    for obj in mesh_objects:
        bake_object_to_world_space(obj)
    active = mesh_objects[0]
    select_only(mesh_objects, active)
    if len(mesh_objects) > 1:
        result = bpy.ops.object.join()
        if "FINISHED" not in result:
            raise FatalPipelineError(f"Mesh join failed: {sorted(result)}")
    active.name = object_name
    active.data.name = f"{object_name}_Mesh"
    active.matrix_world = Matrix.Identity(4)
    return active


def ensure_collection(name: str) -> bpy.types.Collection:
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    return collection


def move_to_collection(obj: bpy.types.Object, collection: bpy.types.Collection) -> None:
    if obj.name not in collection.objects:
        collection.objects.link(obj)
    for current in list(obj.users_collection):
        if current != collection:
            current.objects.unlink(obj)


def mesh_bounds(obj: bpy.types.Object) -> dict[str, Vector | float]:
    if not obj.data.vertices:
        raise PipelineError(f"Mesh is empty: {obj.name}")
    points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    minimum = Vector(tuple(min(point[i] for point in points) for i in range(3)))
    maximum = Vector(tuple(max(point[i] for point in points) for i in range(3)))
    size = maximum - minimum
    return {
        "minimum": minimum,
        "maximum": maximum,
        "center": (minimum + maximum) * 0.5,
        "size": size,
        "diagonal": size.length,
    }


def projection_values(bounds, mode: str, ratio: float, ray: float, cage: float):
    if mode == "AUTO":
        diagonal = float(bounds["diagonal"])
        if not math.isfinite(diagonal) or diagonal <= 1e-12:
            raise PipelineError("Bounding Box diagonal is zero")
        return 0.0, diagonal * ratio
    return ray, cage


def clean_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return cleaned or "Object"


def resolve_output_directory(raw_path: str) -> Path:
    if not raw_path.strip():
        raise PipelineError("Output Directory is empty")
    path = Path(bpy.path.abspath(raw_path)).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_alignment(high: bpy.types.Object, low: bpy.types.Object) -> None:
    high_bounds = mesh_bounds(high)
    low_bounds = mesh_bounds(low)
    diagonal = float(high_bounds["diagonal"])
    center_ratio = (
        Vector(low_bounds["center"]) - Vector(high_bounds["center"])
    ).length / diagonal
    size_ratio = (
        Vector(low_bounds["size"]) - Vector(high_bounds["size"])
    ).length / diagonal
    log(f"Bounding Box delta ratios: center={center_ratio:.6f}, size={size_ratio:.6f}")
    if center_ratio > 0.01:
        log("WARNING: High/Low bounding-box center mismatch exceeds 0.01")
    if size_ratio > 0.05:
        log("WARNING: High/Low bounding-box size mismatch exceeds 0.05")
