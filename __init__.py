bl_info = {
    "name": "ADDON_NAME",
    "author": "AUTHOR_NAME",
    "description": "",
    "blender": (2, 80, 0),
    "version": (0, 1, 0),
    "location": "File > Import",
    "category": "Import-Export",
}


import logging
from pathlib import Path
from typing import cast

import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import CollectionProperty, FloatProperty, StringProperty
from bpy.types import Operator, OperatorFileListElement, Context

from . import reader
from .p3d_importer import P3DImporter
from .ptx_importer import PTXImporter

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
logger.addHandler(handler)
logger.propagate = False


class IMPORT_OT_SCENE_p3d(Operator, ImportHelper):
    """Load a P3D file."""

    bl_idname = "import_scene.p3d"
    bl_label = "Import P3D"
    filename_ext = ".p3d"

    filter_glob: StringProperty(
        default="*.p3d;",
        options={"HIDDEN"},
        maxlen=255,
    )

    directory: StringProperty(
        subtype="DIR_PATH",
        options={"SKIP_SAVE", "HIDDEN"},
    )

    files: CollectionProperty(
        type=OperatorFileListElement,
        options={"SKIP_SAVE", "HIDDEN"},
    )

    bone_length: FloatProperty(
        name="Bone Length",
        description="The length of each bone.",
        default=0.2,
        min=0.0,
        subtype="DISTANCE",
    )

    def execute(self, context: Context):
        for in_path_str in self.files:
            in_path: Path = Path(self.directory) / in_path_str.name
            with open(in_path, "rb") as f:
                header_entry, root_entries = reader.read_file(f)

            importer = P3DImporter(context, self.bone_length)
            importer.import_scene(header_entry, root_entries)
        return {"FINISHED"}


class IMPORT_OT_IMAGE_ptx(Operator, ImportHelper):
    """Load a PTX file."""

    bl_idname = "import_scene.ptx"
    bl_label = "Import PTX"
    filename_ext = ".ptx"

    filter_glob: StringProperty(
        default="*.ptx",
        options={"HIDDEN"},
        maxlen=255,
    )

    directory: StringProperty(
        subtype="DIR_PATH",
        options={"SKIP_SAVE", "HIDDEN"},
    )

    files: CollectionProperty(
        type=OperatorFileListElement,
        options={"SKIP_SAVE", "HIDDEN"},
    )

    def execute(self, context: Context):
        for in_path_str in self.files:
            in_path: Path = Path(self.directory) / in_path_str.name
            with open(in_path, "rb") as f:
                header_entry, root_entries = reader.read_file(f)

            importer = PTXImporter(context)
            importer.import_patx(
                cast(reader.PATXHeaderEntry, header_entry), root_entries, in_path.stem
            )
        return {"FINISHED"}


def menu_func_import(self, context):
    self.layout.operator(
        IMPORT_OT_SCENE_p3d.bl_idname, text="TT Isle of Man Scene (.p3d)"
    )
    self.layout.operator(
        IMPORT_OT_IMAGE_ptx.bl_idname, text="TT Isle of Man Texture (.ptx)"
    )


def register():
    bpy.utils.register_class(IMPORT_OT_SCENE_p3d)
    bpy.utils.register_class(IMPORT_OT_IMAGE_ptx)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.utils.unregister_class(IMPORT_OT_SCENE_p3d)
    bpy.utils.unregister_class(IMPORT_OT_IMAGE_ptx)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


if __name__ == "__main__":
    register()
