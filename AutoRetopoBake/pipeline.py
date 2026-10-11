from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Callable

import bmesh
import bpy

from . import autoremesher, bake
from .utils import (
    PipelineError,
    bake_object_to_world_space,
    clean_name,
    ensure_collection,
    join_meshes_world_space,
    log,
    mesh_bounds,
    move_to_collection,
    projection_values,
    resolve_output_directory,
    validate_alignment,
)


ProgressCallback = Callable[[int, int, str], None]


@dataclass(frozen=True)
class RunOptions:
    target_quads: int
    map_resolution: int
    merge_distance: float
    smart_uv_island_margin: float
    projection_mode: str
    auto_projection_ratio: float
    manual_ray_distance: float
    manual_cage_extrusion: float
    diffuse_bake: bool
    normal_bake: bool
    output_directory: str


@dataclass
class PipelineResult:
    high: bpy.types.Object
    low: bpy.types.Object
    ray_distance: float
    cage_extrusion: float
    diffuse_path: Path | None
    normal_path: Path | None
    blend_path: Path | None


def options_from_properties(settings) -> RunOptions:
    return RunOptions(
        target_quads=settings.target_quads,
        map_resolution=int(settings.map_resolution),
        merge_distance=settings.merge_distance,
        smart_uv_island_margin=settings.smart_uv_island_margin,
        projection_mode=settings.projection_mode,
        auto_projection_ratio=settings.auto_projection_ratio,
        manual_ray_distance=settings.manual_ray_distance,
        manual_cage_extrusion=settings.manual_cage_extrusion,
        diffuse_bake=settings.diffuse_bake,
        normal_bake=settings.normal_bake,
        output_directory=settings.output_directory,
    )


def import_glb(input_path: Path) -> list[bpy.types.Object]:
    before = {obj.as_pointer() for obj in bpy.data.objects}
    result = bpy.ops.import_scene.gltf(
        filepath=str(input_path),
        import_pack_images=True,
        import_select_created_objects=True,
    )
    if "FINISHED" not in result:
        raise PipelineError(f"GLB import failed: {sorted(result)}")
    meshes = [
        obj for obj in bpy.data.objects
        if obj.as_pointer() not in before and obj.type == "MESH" and obj.data.polygons
    ]
    if not meshes:
        raise PipelineError("GLB contains no non-empty Mesh")
    return meshes


def merge_by_distance(high: bpy.types.Object, distance: float) -> tuple[int, int]:
    before = len(high.data.vertices)
    bm = bmesh.new()
    try:
        bm.from_mesh(high.data)
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=distance)
        bm.normal_update()
        bm.to_mesh(high.data)
    finally:
        bm.free()
    high.data.update()
    after = len(high.data.vertices)
    if not after or not high.data.polygons:
        raise PipelineError("Merge by Distance produced an empty mesh")
    return before, after


def save_blend_copy(output_path: Path) -> None:
    result = bpy.ops.wm.save_as_mainfile(
        filepath=str(output_path),
        check_existing=False,
        compress=True,
        copy=True,
    )
    if "FINISHED" not in result or not output_path.is_file():
        raise PipelineError(f"BLEND copy save failed: {output_path}")


def process_high(
    remesh_high: bpy.types.Object,
    base_name: str,
    options: RunOptions,
    preferences,
    progress: ProgressCallback | None = None,
    bake_source: bpy.types.Object | None = None,
) -> PipelineResult:
    bake_high = bake_source if bake_source is not None else remesh_high
    output_dir = resolve_output_directory(options.output_directory)
    stem = clean_name(base_name)
    work_dir = Path(tempfile.mkdtemp(prefix=f"AutoRetopoBake_{stem}_"))
    input_obj = work_dir / f"{stem}_high.obj"
    remeshed_obj = work_dir / f"{stem}_remeshed.obj"
    report_path = work_dir / f"{stem}_report.txt"

    before, after = merge_by_distance(remesh_high, options.merge_distance)
    log(f"Merge by Distance: {before} -> {after} vertices")
    if progress:
        progress(3, 9, "Export OBJ")
    autoremesher.export_obj(remesh_high, input_obj, include_uv=False)
    if progress:
        progress(4, 9, "Run AutoRemesher")
    autoremesher.run(preferences, input_obj, remeshed_obj, report_path, options.target_quads)
    if progress:
        progress(5, 9, "Import remeshed OBJ")
    low = autoremesher.import_obj(remeshed_obj, f"{stem}_LP")
    move_to_collection(low, ensure_collection("AutoRetopo_LP"))
    validate_alignment(remesh_high, low)
    if progress:
        progress(6, 9, "Smart UV")
    bake.smart_uv(low, options.smart_uv_island_margin)

    bounds = mesh_bounds(remesh_high)
    ray, cage = projection_values(
        bounds,
        options.projection_mode,
        options.auto_projection_ratio,
        options.manual_ray_distance,
        options.manual_cage_extrusion,
    )
    log(f"Projection: mode={options.projection_mode}, ray={ray:.6g}, cage={cage:.6g}")
    material = bake.setup_material(low)
    diffuse_path = output_dir / f"{stem}_diffuse.png" if options.diffuse_bake else None
    normal_path = output_dir / f"{stem}_normal.png" if options.normal_bake else None
    with bake.bake_session():
        if options.diffuse_bake:
            if progress:
                progress(7, 9, "Bake Diffuse")
            bake.bake_diffuse(
                bake_high,
                low,
                material,
                diffuse_path,
                options.map_resolution,
                ray,
                cage,
            )
        if options.normal_bake:
            if progress:
                progress(8, 9, "Bake Normal")
            bake.bake_normal(
                bake_high,
                low,
                material,
                normal_path,
                options.map_resolution,
                ray,
                cage,
            )
    bake.validate_material(material, options.diffuse_bake, options.normal_bake)
    autoremesher.export_obj(low, output_dir / f"{stem}_low.obj", include_uv=True)
    log(f"Temporary files: {work_dir}")
    return PipelineResult(bake_high, low, ray, cage, diffuse_path, normal_path, None)


def run_glb_file(
    input_path: Path,
    options: RunOptions,
    preferences,
    progress: ProgressCallback | None = None,
) -> PipelineResult:
    if not input_path.is_file() or input_path.suffix.lower() != ".glb":
        raise PipelineError(f"Invalid GLB file: {input_path}")
    if progress:
        progress(1, 9, "Import GLB")
    meshes = import_glb(input_path)
    high = join_meshes_world_space(meshes, f"{clean_name(input_path.stem)}_HP")
    move_to_collection(high, ensure_collection("AutoRetopo_HP"))
    if progress:
        progress(2, 9, "Merge by Distance")
    result = process_high(high, input_path.stem, options, preferences, progress)
    if progress:
        progress(9, 9, "Save results")
    output_dir = resolve_output_directory(options.output_directory)
    blend_path = output_dir / f"{clean_name(input_path.stem)}_retopo.blend"
    save_blend_copy(blend_path)
    result.blend_path = blend_path
    return result


def remove_temporary_mesh_object(obj: bpy.types.Object | None) -> None:
    if obj is None or obj.name not in bpy.data.objects:
        return
    mesh = obj.data if obj.type == "MESH" else None
    bpy.data.objects.remove(obj, do_unlink=True)
    if mesh is not None and mesh.users == 0:
        bpy.data.meshes.remove(mesh)


def duplicate_selected_for_remesh(source: bpy.types.Object) -> bpy.types.Object:
    if source.type != "MESH" or not source.data.polygons:
        raise PipelineError(f"Selected object has no polygons: {source.name}")
    temporary = source.copy()
    temporary.data = source.data.copy()
    temporary.name = f"__ARB_TMP_{clean_name(source.name)}"
    bpy.context.scene.collection.objects.link(temporary)
    copied_mesh = temporary.data
    try:
        bake_object_to_world_space(temporary)
    except Exception:
        remove_temporary_mesh_object(temporary)
        raise
    if copied_mesh.users == 0:
        bpy.data.meshes.remove(copied_mesh)
    return temporary


def run_selected_object(
    source: bpy.types.Object,
    options: RunOptions,
    preferences,
    progress: ProgressCallback | None = None,
) -> PipelineResult:
    log(f"Selected Object source: {source.name}")
    if progress:
        progress(1, 9, "Prepare Object")
    temporary = None
    try:
        temporary = duplicate_selected_for_remesh(source)
        if progress:
            progress(2, 9, "Merge by Distance")
        result = process_high(
            temporary,
            source.name,
            options,
            preferences,
            progress=progress,
            bake_source=source,
        )
        if progress:
            progress(9, 9, "Save Results")
        return result
    finally:
        remove_temporary_mesh_object(temporary)


def save_batch_blend(options: RunOptions) -> Path:
    output_dir = resolve_output_directory(options.output_directory)
    blend_path = output_dir / "AutoRetopoBatch_retopo.blend"
    save_blend_copy(blend_path)
    return blend_path
