from io import BytesIO
import struct
from typing import Literal

from mathutils import Matrix


class BinaryWriter(BytesIO):
    def __init__(self, big_endian=False) -> None:
        self.endian_symbol: Literal["<", ">"]
        self.byte_order: Literal["little", "big"]
        if big_endian:
            self.endian_symbol = ">"
            self.byte_order = "big"
        else:
            self.endian_symbol = "<"
            self.byte_order = "little"

    def write_uint8(self, value: int) -> None:
        self.write(value.to_bytes(1, signed=False, byteorder=self.byte_order))

    def write_int8(self, value: int) -> None:
        self.write(value.to_bytes(1, signed=True, byteorder=self.byte_order))

    def write_uint16(self, value: int) -> None:
        self.write(value.to_bytes(2, signed=False, byteorder=self.byte_order))

    def write_int16(self, value: int) -> None:
        self.write(value.to_bytes(2, signed=True, byteorder=self.byte_order))

    def write_uint32(self, value: int) -> None:
        self.write(value.to_bytes(4, signed=False, byteorder=self.byte_order))

    def write_int32(self, value: int) -> None:
        self.write(value.to_bytes(4, signed=True, byteorder=self.byte_order))

    def write_float(self, value: float) -> None:
        self.write(struct.pack(self.endian_symbol + "f", value))

    def write_vec2f(self, value: tuple[float, float]) -> None:
        self.write(struct.pack(self.endian_symbol + "2f", *value))

    def write_vec3f(self, value: tuple[float, float, float]) -> None:
        self.write(struct.pack(self.endian_symbol + "3f", *value))

    def write_vec4f(self, value: tuple[float, float, float, float]) -> None:
        self.write(struct.pack(self.endian_symbol + "4f", *value))

    def write_matrix_4x4(self, value: Matrix) -> None:
        value.transpose()
        for row in value:
            self.write_vec4f(row.to_tuple())

    def read_string(self, value: str) -> None:
        self.write(value.encode("ascii", errors="ignore"))
