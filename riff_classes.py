from dataclasses import dataclass, field

from mathutils import Matrix


@dataclass
class Entry:
    tag: str
    size: int


@dataclass
class HeaderEntry(Entry):
    platform: str = "PC"


@dataclass
class PATXHeaderEntry(HeaderEntry):
    pixel_format: str = "DXT1"
    width: int = 1
    height: int = 1
    level_count: int = 0


@dataclass
class ListEntry(Entry):
    element_type: str = ""
    elements: list[Entry] = field(default_factory=list)


@dataclass
class NodeHeEntry(Entry):
    name: str = ""
    transform: Matrix = Matrix()
    child_count: int = 0


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
class BufferEntry(Entry):
    data: bytes


@dataclass
class SkinEntry(Entry):
    skin_meshes: list[SkinMesh] = field(default_factory=list)


@dataclass
class LODsEntry(Entry):
    unk_int16: int = 0
    distances: list[float] = field(default_factory=list)


@dataclass
class RTableEntry(Entry):
    unk_int16: int = 0
    names: list[str] = field(default_factory=list)
