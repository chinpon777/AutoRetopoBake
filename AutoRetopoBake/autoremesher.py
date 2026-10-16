from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import time

import bpy

from .utils import (
    FatalPipelineError,
    PipelineError,
    join_meshes_world_space,
    log,
    select_only,
)


def export_obj(obj: bpy.types.Object, output_obj: Path, include_uv: bool) -> None:
    select_only([obj], obj)
    result = bpy.ops.wm.obj_export(
        filepath=str(output_obj),
        check_existing=False,
        export_selected_objects=True,
        apply_modifiers=True,
        apply_transform=True,
        forward_axis="NEGATIVE_Z",
        up_axis="Y",
        global_scale=1.0,
        export_uv=include_uv,
        export_normals=True,
        export_materials=False,
        export_triangulated_mesh=False,
    )
    if "FINISHED" not in result or not output_obj.is_file():
        raise PipelineError(f"OBJ export failed: {output_obj}")


def run(
    preferences,
    input_obj: Path,
    output_obj: Path,
    report_path: Path,
    target_quads: int,
) -> float:
    executable = Path(bpy.path.abspath(preferences.autoremesher_path)).expanduser()
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise FatalPipelineError(
            f"AutoRemesher is missing or not executable: {executable}"
        )
    base_command = [
        str(executable),
        "--input", str(input_obj),
        "--output", str(output_obj),
        "--report", str(report_path),
        "--target-quads", str(target_quads),
        "--edge-scaling", "1.0",
        "--sharp-edge", "150.0",
        "--smooth-normal", "0.0",
        "--adaptivity", "1.0",
        "--anisotropy", "1.0",
    ]
    command = base_command
    env = os.environ.copy()
    if executable.suffix.lower() == ".appimage" and preferences.appimage_extract_and_run:
        env["APPIMAGE_EXTRACT_AND_RUN"] = "1"
    if not (env.get("DISPLAY") or env.get("WAYLAND_DISPLAY")):
        xvfb_value = preferences.xvfb_run_path.strip()
        xvfb = Path(bpy.path.abspath(xvfb_value)).expanduser() if xvfb_value else None
        if xvfb is None:
            found = shutil.which("xvfb-run")
            xvfb = Path(found) if found else None
        if xvfb is not None and xvfb.is_file():
            command = [str(xvfb), "-a", *base_command]
        else:
            log("WARNING: no display or xvfb-run; AutoRemesher may fail")

    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=input_obj.parent,
            check=False,
            capture_output=True,
            text=True,
            env=env,
            timeout=preferences.timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise PipelineError(f"AutoRemesher timed out after {preferences.timeout_seconds}s") from exc
    except OSError as exc:
        raise FatalPipelineError(f"Could not start AutoRemesher: {exc}") from exc
    elapsed = time.perf_counter() - started
    log(f"AutoRemesher return code: {completed.returncode}")
    if completed.stdout.strip():
        log(f"AutoRemesher stdout:\n{completed.stdout.rstrip()}")
    if completed.stderr.strip():
        log(f"AutoRemesher stderr:\n{completed.stderr.rstrip()}")
    log(f"AutoRemesher execution time: {elapsed:.2f}s")
    if completed.returncode != 0:
        raise PipelineError(f"AutoRemesher failed with return code {completed.returncode}")
    if not output_obj.is_file() or output_obj.stat().st_size == 0:
        raise PipelineError("AutoRemesher did not create a non-empty OBJ")
    return elapsed


def import_obj(input_obj: Path, object_name: str) -> bpy.types.Object:
    before = {obj.as_pointer() for obj in bpy.data.objects}
    result = bpy.ops.wm.obj_import(
        filepath=str(input_obj),
        forward_axis="NEGATIVE_Z",
        up_axis="Y",
        global_scale=1.0,
        use_split_objects=False,
        use_split_groups=False,
        validate_meshes=True,
    )
    if "FINISHED" not in result:
        raise PipelineError(f"OBJ import failed: {sorted(result)}")
    meshes = [
        obj for obj in bpy.data.objects
        if obj.as_pointer() not in before and obj.type == "MESH" and obj.data.polygons
    ]
    if not meshes:
        raise PipelineError("Remeshed OBJ contains no Mesh")
    return join_meshes_world_space(meshes, object_name)
