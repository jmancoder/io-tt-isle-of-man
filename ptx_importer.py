import logging
from typing import cast

import bpy
from bpy.types import Context
import numpy as np
import texture2ddecoder

from . import riff_classes as riff

logger = logging.getLogger(__name__)


class PTXImporter:
    def __init__(self, context: Context) -> None:
        self.context = context
        self.header_entry: riff.PATXHeaderEntry
        self.scene_name: str = ""

    def import_image(self, pixel_buf: bytes) -> None:
        header = cast(riff.PATXHeaderEntry, self.header_entry)
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

    def import_list(self, list_entry: riff.ListEntry) -> None:
        if list_entry.element_type != "Surf":
            logger.warning(
                "Skipping unimplemented list type %s", list_entry.element_type
            )

        # Import first level from surface list
        level_list = cast(riff.ListEntry, list_entry.elements[0])
        pixel_buf = b"".join(
            [
                pixel_entry.data
                for pixel_entry in cast(list[riff.BufferEntry], level_list.elements)
            ]
        )
        self.import_image(pixel_buf)

    def import_patx(
        self,
        header_entry: riff.PATXHeaderEntry,
        root_entries: list[riff.Entry],
        name: str,
    ) -> None:
        self.scene_name = name
        self.header_entry = header_entry
        for entry in root_entries:
            if entry.tag == "LIST":
                self.import_list(cast(riff.ListEntry, entry))
            else:
                logger.warning("Skipping entry of type %s in PATX root", entry.tag)
