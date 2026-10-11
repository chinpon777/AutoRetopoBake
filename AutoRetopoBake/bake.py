from __future__ import annotations

from contextlib import contextmanager
import math
from pathlib import Path
import time

import bpy
from mathutils import Vector

from .utils import PipelineError, log, select_only


NODE_ROLE_KEY = "auto_retopo_bake_role"
DIFFUSE_IMAGE_ROLE = "DIFFUSE_IMAGE"
NORMAL_IMAGE_ROLE = "NORMAL_IMAGE"
NORMAL_MAP_ROLE = "NORMAL_MAP"


def find_node_by_type(nodes, bl_idname: str):
    return next((node for node in nodes if node.bl_idname == bl_idname), None)


def ensure_node_by_type(nodes, bl_idname: str):
    node = find_node_by_type(nodes, bl_idname)
    return node if node is not None else nodes.new(bl_idname)


def find_role_node(nodes, role: str, bl_idname: str):
    return next(
        (
            node
            for node in nodes
            if node.bl_idname == bl_idname and node.get(NODE_ROLE_KEY) == role
        ),
        None,
    )


def require_socket(node, socket_kind: str, identifier: str):
    sockets = getattr(node, socket_kind)
    socket = next(
        (candidate for candidate in sockets if candidate.identifier == identifier),
        None,
    )
    if socket is None:
        raise PipelineError(
            f"{node.bl_idname} has no {socket_kind} socket identifier {identifier!r}"
        )
    return socket


def replace_input_link(node_tree, from_socket, to_socket) -> None:
    for link in tuple(to_socket.links):
        node_tree.links.remove(link)
    node_tree.links.new(from_socket, to_socket)


def ensure_material_graph(material):
    material.use_nodes = True
    nodes = material.node_tree.nodes
    principled = ensure_node_by_type(nodes, "ShaderNodeBsdfPrincipled")
    output = next(
        (
            node
            for node in nodes
            if node.bl_idname == "ShaderNodeOutputMaterial"
            and getattr(node, "is_active_output", False)
        ),
        None,
    )
    if output is None:
        output = ensure_node_by_type(nodes, "ShaderNodeOutputMaterial")
    normal_map = find_role_node(nodes, NORMAL_MAP_ROLE, "ShaderNodeNormalMap")
    if normal_map is None:
        normal_map = ensure_node_by_type(nodes, "ShaderNodeNormalMap")
        normal_map[NODE_ROLE_KEY] = NORMAL_MAP_ROLE
    normal_map.label = "Baked Normal Map"
    normal_map.space = "TANGENT"
    replace_input_link(
        material.node_tree,
        require_socket(principled, "outputs", "BSDF"),
        require_socket(output, "inputs", "Surface"),
    )
    return principled, output, normal_map


def smart_uv(low: bpy.types.Object, margin: float) -> None:
    select_only([low], low)
    while low.data.uv_layers:
        low.data.uv_layers.remove(low.data.uv_layers[0])
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        bpy.ops.mesh.select_all(action="SELECT")
        result = bpy.ops.uv.smart_project(
            angle_limit=math.radians(66.0),
            island_margin=margin,
            margin_method="SCALED",
            correct_aspect=True,
            scale_to_bounds=False,
        )
        if "FINISHED" not in result:
            raise PipelineError(f"Smart UV failed: {sorted(result)}")
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
    layer = low.data.uv_layers.active
    if layer is None:
        raise PipelineError("Smart UV created no UV layer")
    vectors = [Vector(value.vector) for value in layer.uv]
    if not vectors or len(vectors) != len(low.data.loops):
        raise PipelineError("Smart UV loop count mismatch")
    if any(not math.isfinite(component) for uv in vectors for component in uv):
        raise PipelineError("UV contains non-finite coordinates")
    log(f"UV layer generated: {layer.name}, loops={len(vectors)}")


def setup_material(low: bpy.types.Object) -> bpy.types.Material:
    material = bpy.data.materials.new(name=f"{low.name}_Baked_Material")
    ensure_material_graph(material)
    low.data.materials.clear()
    low.data.materials.append(material)
    for polygon in low.data.polygons:
        polygon.material_index = 0
        polygon.use_smooth = True
    return material


def create_target(
    material,
    name: str,
    resolution: int,
    color_space: str,
    role: str,
    label: str,
):
    image = bpy.data.images.new(name, width=resolution, height=resolution, alpha=False)
    image.colorspace_settings.name = color_space
    node = material.node_tree.nodes.new("ShaderNodeTexImage")
    node[NODE_ROLE_KEY] = role
    node.label = label
    node.image = image
    node.interpolation = "Linear"
    return image, node


def set_active_target(material, target) -> None:
    nodes = material.node_tree.nodes
    if target is None or target.bl_idname != "ShaderNodeTexImage":
        raise PipelineError("Bake target is not an Image Texture node")
    if not any(node == target for node in nodes):
        raise PipelineError("Bake target does not belong to the Low Poly material")
    for node in nodes:
        node.select = False
    target.select = True
    nodes.active = target


def save_image(image, output_path: Path, label: str) -> None:
    image.filepath_raw = str(output_path)
    image.file_format = "PNG"
    image.save()
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise PipelineError(f"{label} save failed: {output_path}")


@contextmanager
def bake_session():
    scene = bpy.context.scene
    previous = {
        "engine": scene.render.engine,
        "file_format": scene.render.image_settings.file_format,
        "color_mode": scene.render.image_settings.color_mode,
        "color_depth": scene.render.image_settings.color_depth,
        "pass_color": scene.render.bake.use_pass_color,
        "pass_direct": scene.render.bake.use_pass_direct,
        "pass_indirect": scene.render.bake.use_pass_indirect,
    }
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    try:
        yield
    finally:
        scene.render.bake.use_pass_color = previous["pass_color"]
        scene.render.bake.use_pass_direct = previous["pass_direct"]
        scene.render.bake.use_pass_indirect = previous["pass_indirect"]
        scene.render.image_settings.file_format = previous["file_format"]
        scene.render.image_settings.color_mode = previous["color_mode"]
        scene.render.image_settings.color_depth = previous["color_depth"]
        scene.render.engine = previous["engine"]


def bake_diffuse(high, low, material, output_path, resolution, ray, cage, margin=16):
    started = time.perf_counter()
    image, target = create_target(
        material,
        output_path.stem,
        resolution,
        "sRGB",
        DIFFUSE_IMAGE_ROLE,
        "Baked Diffuse",
    )
    set_active_target(material, target)
    scene = bpy.context.scene
    scene.render.bake.use_pass_color = True
    scene.render.bake.use_pass_direct = False
    scene.render.bake.use_pass_indirect = False
    select_only([high, low], low)
    result = bpy.ops.object.bake(
        type="DIFFUSE",
        pass_filter={"COLOR"},
        use_selected_to_active=True,
        max_ray_distance=ray,
        cage_extrusion=cage,
        target="IMAGE_TEXTURES",
        margin=margin,
        margin_type="EXTEND",
        use_clear=True,
    )
    if "FINISHED" not in result:
        raise PipelineError(f"Diffuse Bake failed: {sorted(result)}")
    save_image(image, output_path, "Diffuse")
    principled, _output, _normal_map = ensure_material_graph(material)
    replace_input_link(
        material.node_tree,
        require_socket(target, "outputs", "Color"),
        require_socket(principled, "inputs", "Base Color"),
    )
    elapsed = time.perf_counter() - started
    log(f"Diffuse Bake complete: {resolution}x{resolution}, sRGB, {elapsed:.2f}s")
    return image


def bake_normal(high, low, material, output_path, resolution, ray, cage, margin=16):
    started = time.perf_counter()
    image, target = create_target(
        material,
        output_path.stem,
        resolution,
        "Non-Color",
        NORMAL_IMAGE_ROLE,
        "Baked Normal",
    )
    set_active_target(material, target)
    select_only([high, low], low)
    result = bpy.ops.object.bake(
        type="NORMAL",
        use_selected_to_active=True,
        max_ray_distance=ray,
        cage_extrusion=cage,
        normal_space="TANGENT",
        target="IMAGE_TEXTURES",
        margin=margin,
        margin_type="EXTEND",
        use_clear=True,
    )
    if "FINISHED" not in result:
        raise PipelineError(f"Normal Bake failed: {sorted(result)}")
    save_image(image, output_path, "Normal")
    principled, _output, normal_map = ensure_material_graph(material)
    replace_input_link(
        material.node_tree,
        require_socket(target, "outputs", "Color"),
        require_socket(normal_map, "inputs", "Color"),
    )
    replace_input_link(
        material.node_tree,
        require_socket(normal_map, "outputs", "Normal"),
        require_socket(principled, "inputs", "Normal"),
    )
    elapsed = time.perf_counter() - started
    log(f"Normal Bake complete: {resolution}x{resolution}, Non-Color, {elapsed:.2f}s")
    return image


def validate_material(material, diffuse_enabled: bool, normal_enabled: bool) -> None:
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    bsdf = find_node_by_type(nodes, "ShaderNodeBsdfPrincipled")
    if bsdf is None:
        raise PipelineError("Principled BSDF is missing")
    if diffuse_enabled:
        target = find_role_node(nodes, DIFFUSE_IMAGE_ROLE, "ShaderNodeTexImage")
        if target is None or not any(
            link.from_node == target
            and link.to_socket == require_socket(bsdf, "inputs", "Base Color")
            for link in links
        ):
            raise PipelineError("Diffuse texture is not connected")
    if normal_enabled:
        target = find_role_node(nodes, NORMAL_IMAGE_ROLE, "ShaderNodeTexImage")
        normal_map = find_role_node(nodes, NORMAL_MAP_ROLE, "ShaderNodeNormalMap")
        if target is None or normal_map is None:
            raise PipelineError("Normal nodes are missing")
        if not any(link.from_node == target and link.to_node == normal_map for link in links):
            raise PipelineError("Normal image is not connected to Normal Map")
        if not any(
            link.from_node == normal_map
            and link.to_socket == require_socket(bsdf, "inputs", "Normal")
            for link in links
        ):
            raise PipelineError("Normal Map is not connected to BSDF")
