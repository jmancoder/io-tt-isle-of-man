from dataclasses import dataclass, field
from io import BufferedReader
import logging

import numpy as np
import numpy.typing as npt
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
    list_type: str = ""
    child_entries: list[Entry] = field(default_factory=list)


@dataclass
class NodeEntry(Entry):
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
    vertex_count: int
    tri_count: int


@dataclass
class GEBufferEntry(Entry):
    buffer: npt.NDArray


def read_entry(bs: BinaryReader) -> Entry:
    tag = bs.read_string(4)
    size = bs.read_uint32()
    end_off = bs.tell() + size
    logger.debug("Reading entry %s of size %u at 0x%X", tag, size, bs.tell() - 8)

    match tag:
        case "LIST":
            entry = ListEntry(tag, size)
            entry.list_type = bs.read_string(4)
            while bs.tell() < end_off:
                entry.child_entries.append(read_entry(bs))

        case "NoHe":
            entry = NodeEntry(tag, size)
            bs.read_int16()
            name_len = bs.read_uint16()
            entry.name = bs.read_string(name_len)
            bs.read_int16()
            entry.transform = bs.read_matrix_4x4()
            bs.read_int16()
            bs.read_int32()
            bs.read_int32()
            bs.read_int16()

        case "Node":
            # Data is in previous NoHe entry
            entry = Entry(tag, size)

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
            bs.read_int16()
            vertex_count = bs.read_uint32()
            tri_count = bs.read_uint32()
            bs.read_int16()
            while True:
                entry = read_entry(bs)

        case "vpos":
            entry = GEBufferEntry(
                tag, size, np.frombuffer(bs.read(size), "<f4").reshape(-1, 3)
            )
        case "vski":
            entry = GEBufferEntry(
                tag, size, np.frombuffer(bs.read(size), "<u4").reshape(-1, 2)
            )
        case "vnor":
            # Needs to be unpacked somehow
            entry = GEBufferEntry(
                tag, size, np.frombuffer(bs.read(size), "<u4").reshape(-1, 2)
            )
        case "vtan":
            entry = GEBufferEntry(tag, size, np.frombuffer(bs.read(size), "<u4"))
        case "vuvs":
            entry = GEBufferEntry(
                tag, size, np.frombuffer(bs.read(size), "<u4").reshape(-1, 2)
            )
        case "vcol":
            entry = GEBufferEntry(
                tag, size, np.frombuffer(bs.read(size), "<u1").reshape(-1, 4)
            )
        case "indx":
            # Read triangle indices
            entry = GEBufferEntry(
                tag, size, np.frombuffer(bs.read(size), "<u2").reshape(-1, 3)
            )
        case "EndG":
            # Marks the end of a GE buffer list
            entry = Entry(tag, size)
        case _:
            raise NotImplementedError(
                f"Unimplemented entry tag {tag} at {bs.tell() - 8}"
            )

    bs.seek(end_off)
    return entry


def read_file(f: BufferedReader) -> None:
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
