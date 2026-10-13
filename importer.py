import logging
from typing import cast

import bpy
from bpy.types import Context

from . import reader

logger = logging.getLogger(__name__)


def import_node_he(context: Context, node_entry: reader.NodeHeEntry) -> None:
    node_obj = bpy.data.objects.new(node_entry.name, None)
    node_obj.empty_display_size = 0.1
    node_obj.matrix_world = node_entry.transform
    context.collection.objects.link(node_obj)


def import_list(context: Context, list_entry: reader.ListEntry) -> None:
    match list_entry.element_type:
        case "Nods":
            # Import node list
            for child_entry in list_entry.elements:
                if child_entry.tag == "NoHe":
                    import_node_he(context, cast(reader.NodeHeEntry, child_entry))
                elif child_entry.tag == "Node":
                    continue
                elif child_entry.tag == "LIST":
                    import_list(context, cast(reader.ListEntry, child_entry))
                else:
                    logger.warning("Skipping %s entry in node list", child_entry.tag)

        case "MeLi":
            # Import mesh list
            mesh_entry = cast(reader.MeshEntry, list_entry.elements[0])
            geom_list_entry = cast(reader.ListEntry, list_entry.elements[1])
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
            import_list(context, geom_list_entry)

        case "GeLi":
            # Import geometry list
            geom_entry = cast(reader.GeometryEntry, list_entry.elements[0])
            ge_list_entry = cast(reader.ListEntry, list_entry.elements[1])
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
            import_list(context, ge_list_entry)

        case "SGLi":
            # Import geometry list
            ge_entry = cast(reader.GEEntry, list_entry.elements[0])
            if ge_entry.tag != "SuGe":
                logger.error(
                    "Expected SuGe tag on first SG list element; got %s",
                    ge_entry.tag,
                )
                return
            for i in range(1, len(list_entry.elements) - 1):
                buf_entry = cast(reader.GEBufferEntry, list_entry.elements[i])
                # TODO: Import meshes

        case _:
            logger.warning(
                "Skipping unimplemented list type %s", list_entry.element_type
            )


def import_scene(context: Context, entries: list[reader.Entry]) -> None:
    import_list(context, cast(reader.ListEntry, entries[0]))
