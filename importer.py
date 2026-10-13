import logging
from typing import cast

import bpy
from bpy.types import Context, Object
import numpy as np

from . import reader

logger = logging.getLogger(__name__)


def import_node_he(
    context: Context, node_entry: reader.NodeHeEntry, parent_obj: Object | None
) -> Object:
    node_obj = bpy.data.objects.new(node_entry.name, None)
    node_obj.empty_display_size = 0.1
    node_obj.parent = parent_obj
    node_obj.matrix_basis = node_entry.transform
    context.collection.objects.link(node_obj)
    return node_obj


def import_mesh(
    context: Context,
    ge_entry: reader.GEEntry,
    buffers: list[reader.GEBufferEntry],
    parent_obj: Object | None,
) -> Object | None:
    # Create NumPy arrays from raw buffers
    positions = None
    uvs = None
    triangles = []
    for buffer in buffers:
        match buffer.tag:
            case "vpos":
                positions = np.frombuffer(
                    buffer.data, "<f4", ge_entry.vertex_count * 3
                ).reshape(-1, 3)

            case "vuvs":
                stride = len(buffer.data) // ge_entry.vertex_count
                if stride == 8:
                    uvs = np.frombuffer(
                        buffer.data, "<u4", ge_entry.vertex_count * 2
                    ).astype("<f4")
                    uvs /= 268435456.0
                elif stride == 4:
                    uvs = np.frombuffer(
                        buffer.data, "<u2", ge_entry.vertex_count * 2
                    ).astype("<f4")
                    uvs /= 4096.0
                else:
                    logger.error("Unexpected vuvs buffer stride %d", stride)
                    continue
                uvs = uvs.reshape(-1, 2)

            case "indx":
                triangles = np.frombuffer(
                    buffer.data, "<u2", ge_entry.tri_count * 3
                ).reshape(-1, 3)

    if positions is None:
        return None

    # Create mesh from geometry
    mesh = bpy.data.meshes.new("Mesh")
    mesh.from_pydata(positions, [], triangles)
    mesh.validate()
    mesh.update()

    # Import UVs
    if uvs is not None:
        uvs[:, 1] = 1.0 - uvs[:, 1]
        uv_layer = mesh.uv_layers.new()
        vertex_idx_array = np.empty(len(mesh.loops), dtype=np.int32)
        mesh.loops.foreach_get("vertex_index", vertex_idx_array)
        uv_layer.uv.foreach_set("vector", uvs[vertex_idx_array].ravel())

    # Create object
    if parent_obj is not None:
        mesh_obj = bpy.data.objects.new(parent_obj.name + "_Mesh", mesh)
        mesh_obj.parent = parent_obj
    else:
        mesh_obj = bpy.data.objects.new("Mesh", mesh)
    context.collection.objects.link(mesh_obj)
    return mesh_obj


def import_nods(
    context: Context, list_entry: reader.ListEntry, parent_obj: Object | None
) -> None:
    node_obj = parent_obj
    for entry in list_entry.elements:
        match entry.tag:
            case "NoHe":
                node_obj = import_node_he(
                    context, cast(reader.NodeHeEntry, entry), parent_obj
                )
            case "Node":
                # Empty entry; data is in previous NoHe entry
                pass
            case "LIST":
                import_list(context, cast(reader.ListEntry, entry), node_obj)
            case _:
                logger.warning("Skipping %s entry in node list", entry.tag)


def import_list(
    context: Context, list_entry: reader.ListEntry, parent_obj: Object | None
) -> None:
    match list_entry.element_type:
        case "Nods":
            import_nods(context, list_entry, parent_obj)

        case "MeLi":
            # Import mesh list
            mesh_entry = list_entry.elements[0]
            geom_list_entry = list_entry.elements[1]
            if mesh_entry.tag != "Mesh":
                logger.error(
                    "Expected Mesh tag on first mesh list element; got %s",
                    mesh_entry.tag,
                )
                return
            if geom_list_entry.tag != "LIST":
                logger.error(
                    "Expected LIST tag on second mesh list element; got %s",
                    geom_list_entry.tag,
                )
                return
            import_list(context, cast(reader.ListEntry, geom_list_entry), parent_obj)

        case "GeLi":
            # Import geometry list
            geom_entry = list_entry.elements[0]
            ge_list_entry = list_entry.elements[1]
            if geom_entry.tag != "Geom":
                logger.error(
                    "Expected Geom tag on first geometry list element; got %s",
                    geom_entry.tag,
                )
                return
            if ge_list_entry.tag != "LIST":
                logger.error(
                    "Expected LIST tag on second geometry list element; got %s",
                    ge_list_entry.tag,
                )
                return
            import_list(context, cast(reader.ListEntry, ge_list_entry), parent_obj)

        case "SGLi":
            # Import GE list
            ge_entry = list_entry.elements[0]
            if ge_entry.tag != "SuGe":
                logger.error(
                    "Expected SuGe tag on first SG list element; got %s",
                    ge_entry.tag,
                )
                return
            import_mesh(
                context,
                cast(reader.GEEntry, ge_entry),
                cast(list[reader.GEBufferEntry], list_entry.elements[1:]),
                parent_obj,
            )

        case _:
            logger.warning(
                "Skipping unimplemented list type %s", list_entry.element_type
            )


def import_scene(context: Context, entries: list[reader.Entry]) -> None:
    for entry in entries:
        if entry.tag == "LIST":
            import_list(context, cast(reader.ListEntry, entry), None)
