import logging
from typing import cast

import bpy
from bpy.types import Armature, Context, Object
import numpy as np

from . import reader

logger = logging.getLogger(__name__)


class P3DImporter:
    def __init__(self, context: Context, bone_length: int) -> None:
        self.context = context
        self.armature_map: dict[str, Object] = {}
        self.header_entry: reader.HeaderEntry
        self.bone_length = bone_length

    def import_empty(
        self, node_entry: reader.NodeHeEntry, parent_obj: Object | None
    ) -> Object:
        # Use existing armature if possible, else create an empty object
        node_obj = self.armature_map.get(node_entry.name)
        if node_obj is None:
            node_obj = bpy.data.objects.new(node_entry.name, None)
            node_obj.empty_display_size = 0.1
            self.context.collection.objects.link(node_obj)

        node_obj.parent = parent_obj
        node_obj.matrix_basis = node_entry.transform
        return node_obj

    def import_mesh(
        self,
        ge_entry: reader.GEEntry,
        buffers: list[reader.BufferEntry],
        parent_obj: Object | None,
    ) -> Object | None:
        # Create NumPy arrays from raw buffers
        positions = None
        weights = None
        indices = None
        normals = None
        uvs = None
        alt_uvs = None
        colors = None
        triangles = None
        for buffer in buffers:
            match buffer.tag:
                case "vpos":
                    positions = np.frombuffer(
                        buffer.data, "<f4", ge_entry.vertex_count * 3
                    ).reshape(-1, 3)

                case "vski":
                    skin_entries = np.frombuffer(
                        buffer.data, "<u1", ge_entry.vertex_count * 8
                    ).reshape(-1, 8)
                    weights = skin_entries[:, :4].astype("<f4") / 255.0
                    indices = skin_entries[:, 4:]

                case "vnor":
                    normals = np.frombuffer(
                        buffer.data, "<f2", ge_entry.vertex_count * 4
                    ).astype(np.float32)
                    normals = normals.reshape(-1, 4)[:, :3]

                case "vuvs":
                    stride = len(buffer.data) // ge_entry.vertex_count
                    if stride == 8:
                        uvs = (
                            np.frombuffer(
                                buffer.data, "<u2", ge_entry.vertex_count * 4
                            ).astype("<f4")
                            / 4096.0
                        )
                        uvs = uvs.reshape(-1, 4)
                        alt_uvs = uvs[:, 2:]
                        uvs = uvs[:, :2]
                    elif stride == 4:
                        uvs = (
                            np.frombuffer(
                                buffer.data, "<u2", ge_entry.vertex_count * 2
                            ).astype("<f4")
                            / 4096.0
                        )
                        uvs = uvs.reshape(-1, 2)
                    else:
                        logger.error("Unexpected vuvs buffer stride %d", stride)
                        continue

                case "vcol":
                    colors = np.frombuffer(
                        buffer.data, "<u1", ge_entry.vertex_count * 4
                    )

                case "indx":
                    triangles = np.frombuffer(
                        buffer.data, "<u2", ge_entry.tri_count * 3
                    ).reshape(-1, 3)

        # Import positions
        if positions is None:
            return None
        mesh = bpy.data.meshes.new("Mesh")
        mesh.vertices.add(len(positions))
        mesh.vertices.foreach_set("co", positions.ravel())

        # Import triangles
        if triangles is not None:
            mesh.loops.add(len(triangles) * 3)
            mesh.loops.foreach_set("vertex_index", triangles.ravel())
            mesh.polygons.add(len(triangles))
            mesh.polygons.foreach_set(
                "loop_start", np.arange(0, len(triangles) * 3, 3, dtype="<i4")
            )
            mesh.polygons.foreach_set(
                "loop_total", np.full(len(triangles), 3, dtype="<i4")
            )
        mesh.update(calc_edges=True)

        # Import normals
        if normals is not None:
            mesh.normals_split_custom_set_from_vertices(normals)

        # Import UVs
        for uv_array in (uvs, alt_uvs):
            if uv_array is not None:
                uv_layer = mesh.uv_layers.new()
                uv_layer.uv.foreach_set("vector", uv_array[triangles.ravel()].ravel())

        # Import colors
        if colors is not None:
            vertex_color_attr = mesh.color_attributes.new(
                name="vertex_color", type="BYTE_COLOR", domain="POINT"
            )
            vertex_color_attr.data.foreach_set("color", colors)

        # Create mesh object
        if parent_obj is not None:
            mesh_obj = bpy.data.objects.new(parent_obj.name + "_Mesh", mesh)
            mesh_obj.parent = parent_obj
        else:
            mesh_obj = bpy.data.objects.new("Mesh", mesh)
        self.context.collection.objects.link(mesh_obj)

        # Add armature modifier and create vertex groups
        if parent_obj is None or type(parent_obj.data) is not Armature:
            return mesh_obj
        modifier = mesh_obj.modifiers.new("Armature", "ARMATURE")
        modifier.object = parent_obj
        vertex_groups = [
            mesh_obj.vertex_groups.new(name=bone.name) for bone in parent_obj.data.bones
        ]

        # Import skin data
        if weights is None or indices is None:
            return mesh_obj
        for i, (weight_group, index_group) in enumerate(zip(weights, indices)):
            for weight, index in zip(weight_group, index_group):
                if weight > 0.0:
                    vertex_groups[index].add([i], weight, "REPLACE")
        return mesh_obj

    def import_nods(
        self, list_entry: reader.ListEntry, parent_obj: Object | None
    ) -> None:
        node_obj = parent_obj
        for entry in list_entry.elements:
            match entry.tag:
                case "NoHe":
                    node_obj = self.import_empty(
                        cast(reader.NodeHeEntry, entry), parent_obj
                    )
                case "Node":
                    # Empty entry; data is in previous NoHe entry
                    pass
                case "LIST":
                    self.import_list(cast(reader.ListEntry, entry), node_obj)
                case _:
                    logger.warning("Skipping %s entry in node list", entry.tag)

    def import_armatures(self, skin_entry: reader.SkinEntry) -> None:
        if skin_entry.tag != "Skin":
            raise TypeError(
                "Expected Skin tag on SkinEntry object; got %s", skin_entry.tag
            )

        for skin_mesh in skin_entry.skin_meshes:
            armature = bpy.data.armatures.new(skin_mesh.name)
            armature_obj = bpy.data.objects.new(skin_mesh.name, armature)
            self.context.collection.objects.link(armature_obj)
            self.armature_map[skin_mesh.name] = armature_obj
            self.context.view_layer.objects.active = armature_obj

            bpy.ops.object.mode_set(mode="EDIT")
            for bone_data in skin_mesh.bones:
                bone = armature.edit_bones.new(bone_data.name)
                bone.length = self.bone_length
                bone.matrix = bone_data.transform.inverted()
            bpy.ops.object.mode_set(mode="OBJECT")

    def import_list(
        self,
        list_entry: reader.ListEntry,
        parent_obj: Object | None,
    ) -> None:
        if list_entry.tag != "LIST":
            raise TypeError(
                "Expected LIST tag on ListEntry object; got %s", list_entry.tag
            )

        match list_entry.element_type:
            case "Nods":
                self.import_nods(list_entry, parent_obj)

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
                self.import_list(
                    cast(reader.ListEntry, geom_list_entry),
                    parent_obj,
                )

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
                self.import_list(
                    cast(reader.ListEntry, ge_list_entry),
                    parent_obj,
                )

            case "SGLi":
                # Import GE list
                ge_entry = list_entry.elements[0]
                if ge_entry.tag != "SuGe":
                    logger.error(
                        "Expected SuGe tag on first SG list element; got %s",
                        ge_entry.tag,
                    )
                    return
                self.import_mesh(
                    cast(reader.GEEntry, ge_entry),
                    cast(list[reader.BufferEntry], list_entry.elements[1:]),
                    parent_obj,
                )

            case _:
                logger.warning(
                    "Skipping unimplemented list type %s", list_entry.element_type
                )

    def import_scene(
        self, header_entry: reader.HeaderEntry, root_entries: list[reader.Entry]
    ) -> None:
        self.header_entry = header_entry
        self.import_armatures(cast(reader.SkinEntry, root_entries[1]))
        self.import_list(cast(reader.ListEntry, root_entries[0]), None)
