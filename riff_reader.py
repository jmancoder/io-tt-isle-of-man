from io import BufferedReader
import logging
from typing import cast

from .binary_reader import BinaryReader
from . import riff_classes as riff

logger = logging.getLogger(__name__)


def read_entry(bs: BinaryReader) -> riff.Entry:
    start_off = bs.tell()
    tag = bs.read_string(4)
    size = bs.read_uint32()
    end_off = bs.tell() + size
    logger.debug("Reading entry %s of size %u at 0x%X", tag, size, start_off)

    match tag:
        case "Head":
            file_type = bs.read_string(8)
            if file_type == "SCENE___":
                entry = riff.HeaderEntry(tag, size)
            elif file_type == "PATX-SP2":
                entry = riff.PATXHeaderEntry(tag, size)
            else:
                raise NotImplementedError(f"Unimplemented file type {file_type}")

            endi_tag = bs.read_string(4)
            bs.read_int32()
            bs.read_int32()
            bs.read_int32()
            bs.read_int32()
            entry.platform = bs.read_string(2)

            if type(entry) is riff.PATXHeaderEntry:
                bs.read_int32()
                bs.read_int16()
                bs.read_int32()
                entry.pixel_format = bs.read_string(4)
                entry.width = bs.read_uint32()
                entry.height = bs.read_uint32()
                bs.read_uint32()
                entry.level_count = bs.read_uint32()
                bs.read_int32()
                bs.read_vec3f()
                bs.read_int32()
                sentinel = bs.read_int16()

        case "LIST":
            entry = riff.ListEntry(tag, size)
            entry.element_type = bs.read_string(4)
            while bs.tell() < end_off:
                entry.elements.append(read_entry(bs))
            logger.debug(
                "Reached end of %s list (0x%X - 0x%X)",
                entry.element_type,
                start_off,
                end_off,
            )

        case "NoHe":
            entry = riff.NodeHeEntry(tag, size)
            bs.read_int16()
            name_len = bs.read_uint32()
            entry.name = bs.read_string(name_len)
            bs.read_int16()
            entry.transform = bs.read_matrix_4x4()
            sentinel = bs.read_int16()
            bs.read_int32()
            entry.child_count = bs.read_int32()
            sentinel = bs.read_int16()

        case "Mesh":
            entry = riff.MeshEntry(tag, size)
            bs.read_int16()
            bs.read_uint8()
            bs.read_int16()
            entry.bounds_min = bs.read_vec3f()
            entry.bounds_max = bs.read_vec3f()
            bs.read_int16()
            bs.read_int16()
            bs.read_int16()
            bs.read_int16()
            bs.read_vec3f()
            bs.read_int16()
            bs.read_int16()
            bs.read_int16()
            bs.read_int16()
            bs.read_int16()
            bs.read_uint8()

        case "Geom":
            entry = riff.GeometryEntry(tag, size)
            bs.read_int16()
            bs.read_uint8()
            bs.read_uint8()
            bs.read_uint8()
            bs.read_int16()
            bs.read_int16()
            bs.read_int16()
            bs.read_uint8()

        case "SuGe":
            entry = riff.GEEntry(tag, size)
            bs.read_int16()
            entry.vertex_count = bs.read_uint32()
            entry.tri_count = bs.read_uint32()
            bs.read_int16()

        case "vpos" | "vski" | "vnor" | "vtan" | "vuvs" | "vcol" | "indx" | "Pixl":
            entry = riff.BufferEntry(tag, size, bs.read(size))

        case "EndG" | "Node":
            entry = riff.Entry(tag, size)

        case "Skin":
            entry = riff.SkinEntry(tag, size)
            bs.read_int16()
            skin_mesh_count = bs.read_uint32()
            for _ in range(skin_mesh_count):
                skin_mesh = riff.SkinMesh()
                bs.read_int16()
                name_len = bs.read_uint32()
                skin_mesh.name = bs.read_string(name_len)
                bs.read_int32()
                bs.read_int32()

                bone_count = bs.read_uint32()
                for _ in range(bone_count):
                    bone = riff.Bone()
                    bs.read_int16()
                    name_len = bs.read_uint32()
                    bone.name = bs.read_string(name_len)
                    bone.transform = bs.read_matrix_4x4()
                    skin_mesh.bones.append(bone)
                    bs.read_int16()

                entry.skin_meshes.append(skin_mesh)
                bs.read_int16()
            bs.read_int16()

        case "LODs":
            entry = riff.LODsEntry(tag, size)
            entry.unk_int16 = bs.read_int16()
            lod_count = bs.read_uint32()
            entry.distances = [bs.read_float() for _ in range(lod_count)]

        case "RTbl":
            entry = riff.RTableEntry(tag, size)
            entry.unk_int16 = bs.read_int16()
            name_count = bs.read_uint32()
            for _ in range(name_count):
                name_len = bs.read_uint32()
                entry.names.append(bs.read_string(name_len))

        case _:
            logger.warning("Skipping unimplemented tag %s at 0x%X", tag, start_off)
            entry = riff.Entry(tag, size)

    bs.seek(end_off)
    return entry


def read_file(f: BufferedReader) -> tuple[riff.HeaderEntry, list[riff.Entry]]:
    bs = BinaryReader(f.read())

    # Read file header
    sig = bs.read_string(4)
    if sig != "RIFF":
        raise ValueError("Missing RIFF file signature")
    file_size = bs.read_uint32() + 8
    pa_tag = bs.read_string(4)

    # Read header entry
    header_entry = cast(riff.HeaderEntry, read_entry(bs))

    # Read root entries
    root_entries: list[riff.Entry] = []
    while bs.tell() < file_size:
        root_entries.append(read_entry(bs))
    return header_entry, root_entries
