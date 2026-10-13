from dataclasses import dataclass, field
from io import BufferedReader
import logging

from mathutils import Matrix

from .binary_reader import BinaryReader

logger = logging.getLogger(__name__)


@dataclass
class Entry:
    tag: str
    size: int


@dataclass
class ListEntry(Entry):
    total_size: int = 0
    size: int = 0
    element_type: str = ""
    elements: list[Entry] = field(default_factory=list)


@dataclass
class NodeHeEntry(Entry):
    name: str = ""
    transform: Matrix = Matrix()


@dataclass
class MeshEntry(Entry):
    bounds_min: tuple[float, float, float] = (0.0, 0.0, 0.0)
    bounds_max: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass
class GeometryEntry(Entry): ...


@dataclass
class GEEntry(Entry):
    vertex_count: int = 0
    tri_count: int = 0


@dataclass
class Bone:
    name: str = ""
    transform: Matrix = Matrix()


@dataclass
class SkinMesh:
    name: str = ""
    bones: list[Bone] = field(default_factory=list)


@dataclass
class GEBufferEntry(Entry):
    data: bytes


@dataclass
class SkinEntry(Entry):
    skin_meshes: list[SkinMesh] = field(default_factory=list)


def read_entry(bs: BinaryReader) -> Entry:
    start_off = bs.tell()
    tag = bs.read_string(4)
    size = bs.read_uint32()
    end_off = bs.tell() + size
    logger.debug("Reading entry %s of size %u at 0x%X", tag, size, start_off)

    match tag:
        case "LIST":
            entry = ListEntry(tag, size)
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
            entry = NodeHeEntry(tag, size)
            bs.read_int16()
            name_len = bs.read_uint32()
            entry.name = bs.read_string(name_len)
            bs.read_int16()
            entry.transform = bs.read_matrix_4x4()
            bs.read_int16()
            bs.read_int32()
            bs.read_int32()
            bs.read_int16()

        case "Mesh":
            entry = MeshEntry(tag, size)
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
            entry = GeometryEntry(tag, size)
            bs.read_int16()
            bs.read_uint8()
            bs.read_uint8()
            bs.read_uint8()
            bs.read_int16()
            bs.read_int16()
            bs.read_int16()
            bs.read_uint8()

        case "SuGe":
            entry = GEEntry(tag, size)
            bs.read_int16()
            entry.vertex_count = bs.read_uint32()
            entry.tri_count = bs.read_uint32()
            bs.read_int16()

        case "vpos" | "vski" | "vnor" | "vtan" | "vuvs" | "vcol" | "indx":
            entry = GEBufferEntry(tag, size, bs.read(size))

        case "EndG" | "Node":
            entry = Entry(tag, size)

        case "Skin":
            entry = SkinEntry(tag, size)
            bs.read_int16()
            skin_mesh_count = bs.read_uint32()
            for _ in range(skin_mesh_count):
                skin_mesh = SkinMesh()
                bs.read_int16()
                name_len = bs.read_uint32()
                skin_mesh.name = bs.read_string(name_len)
                bs.read_int32()
                bs.read_int32()
                bone_count = bs.read_uint32()
                for _ in range(bone_count):
                    bone = Bone()
                    bs.read_int16()
                    name_len = bs.read_uint32()
                    bone.name = bs.read_string(name_len)
                    bone.transform = bs.read_matrix_4x4()
                    skin_mesh.bones.append(bone)
                    bs.read_int16()
                entry.skin_meshes.append(skin_mesh)
                bs.read_int16()
            bs.read_int16()

        case _:
            logger.warning("Skipping unimplemented tag %s at 0x%X", tag, start_off)
            entry = Entry(tag, size)

    bs.seek(end_off)
    return entry


def read_file(f: BufferedReader) -> list[Entry]:
    bs = BinaryReader(f.read())

    # Read file header
    sig = bs.read_string(4)
    if sig != "RIFF":
        raise ValueError("Missing RIFF file signature")
    file_size = bs.read_uint32() + 8
    pa_tag = bs.read_string(4)

    # Read sub-header
    head_tag = bs.read_string(4)
    header_size = bs.read_uint32()
    header_end = bs.tell() + header_size
    file_type = bs.read_string(8)
    endi_tag = bs.read_string(4)
    bs.read_uint32()
    bs.read_uint32()
    bs.read_uint32()
    bs.read_uint32()
    platform = bs.read_string(2)
    if file_type == "SCENE___":
        pass
    else:
        raise NotImplementedError(f"Unimplemented file type {file_type}")
    bs.seek(header_end)

    # Read tagged entries
    entries: list[Entry] = []
    while bs.tell() < file_size:
        entries.append(read_entry(bs))
    return entries
