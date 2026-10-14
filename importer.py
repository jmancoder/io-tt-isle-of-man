import logging
from typing import cast

import bpy
from bpy.types import Context, Object
import numpy as np
import texture2ddecoder

from . import reader

logger = logging.getLogger(__name__)


class Importer:
    def __init__(self, context: Context, bone_length: int) -> None:
        self.context = context
        self.header_entry: reader.HeaderEntry
        self.scene_name: str = ""
        self.bone_length = bone_length

    def import_empty(
        self, node_entry: reader.NodeHeEntry, parent_obj: Object | None
    ) -> Object:
        node_obj = bpy.data.objects.get(node_entry.name)
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
        uvs = None
        alt_uvs = None
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
                        uvs = (
                            np.frombuffer(
                                buffer.data, "<u2", ge_entry.vertex_count * 4
                            ).astype("<f4")
                            / 4096.0
                        )
                        uvs = uvs.reshape(-1, 4)
                        alt_uvs = uvs = uvs[:, 2:]
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
        for uv_array in (uvs, alt_uvs):
            if uv_array is not None:
                uv_layer = mesh.uv_layers.new()
                vertex_idx_array = np.empty(len(mesh.loops), dtype=np.int32)
                mesh.loops.foreach_get("vertex_index", vertex_idx_array)
                uv_layer.uv.foreach_set("vector", uv_array[vertex_idx_array].ravel())

        # Create object
        if parent_obj is not None:
            mesh_obj = bpy.data.objects.new(parent_obj.name + "_Mesh", mesh)
            mesh_obj.parent = parent_obj
        else:
            mesh_obj = bpy.data.objects.new("Mesh", mesh)
        self.context.collection.objects.link(mesh_obj)
        return mesh_obj

    def import_image(self, pixel_buf: bytes) -> None:
        header = cast(reader.PATXHeaderEntry, self.header_entry)
        width = header.width
        height = header.height
        if header.pixel_format == "DXT1":
            bgra_buf = texture2ddecoder.decode_bc1(pixel_buf, width, height)
        elif header.pixel_format == "BC5S":
            bgra_buf = texture2ddecoder.decode_bc5(pixel_buf, width, height)
        else:
            logger.error("Unimplemented pixel format %s", header.pixel_format)
            return

        rgba = np.frombuffer(bgra_buf, "<u1").reshape(-1, 4)[:, [2, 1, 0, 3]].ravel()
        rgba = rgba.astype(np.float32) / 255.0

        image = bpy.data.images.new(self.scene_name, width, height)
        image.pixels = rgba
        image.update()

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

            case "Surf":
                # Import first level from surface list
                level_list = cast(reader.ListEntry, list_entry.elements[0])
                pixel_buf = b"".join(
                    [
                        pixel_entry.data
                        for pixel_entry in cast(
                            list[reader.BufferEntry], level_list.elements
                        )
                    ]
                )
                self.import_image(pixel_buf)

            case _:
                logger.warning(
                    "Skipping unimplemented list type %s", list_entry.element_type
                )

    def import_root_entries(self, entries: list[reader.Entry], name: str) -> None:
        self.scene_name = name
        self.header_entry = cast(reader.HeaderEntry, entries[0])
        if type(self.header_entry) is reader.PATXHeaderEntry:
            # Import PTX texture(s)
            for i in range(1, len(entries)):
                entry = entries[i]
                if entry.tag == "LIST":
                    self.import_list(
                        cast(reader.ListEntry, entry),
                        None,
                    )
                else:
                    logger.warning("Skipping entry of type %s in PATX root", entry.tag)
        else:
            # Import P3D scene
            self.import_armatures(cast(reader.SkinEntry, entries[2]))
            self.import_list(cast(reader.ListEntry, entries[1]), None)
