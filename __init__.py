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

import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import FloatProperty, StringProperty
from bpy.types import Operator, Context

from . import reader
from .importer import Importer

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
logger.addHandler(handler)
logger.propagate = False


class IMPORT_OT_SCENE_p3d(Operator, ImportHelper):
    """Load a P3D/PTX file."""

    bl_idname = "import_scene.p3d_ptx"
    bl_label = "Import P3D/PTX"
    filename_ext = ".p3d;.ptx"

    filter_glob: StringProperty(
        default="*.p3d;*.ptx",
        options={"HIDDEN"},
        maxlen=255,
    )

    bone_length: FloatProperty(
        name="Bone Length",
        description="The length of each bone.",
        default=0.2,
        min=0.0,
        subtype="DISTANCE",
    )

    def execute(self, context: Context):
        in_path = Path(self.filepath)
        with open(in_path, "rb") as f:
            entries = reader.read_file(f)

        data_importer = Importer(context, self.bone_length)
        data_importer.import_root_entries(entries, in_path.stem)
        return {"FINISHED"}


def menu_func_import(self, context):
    self.layout.operator(
        IMPORT_OT_SCENE_p3d.bl_idname, text="TT Isle of Man (.p3d/.ptx)"
    )


def register():
    bpy.utils.register_class(IMPORT_OT_SCENE_p3d)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.utils.unregister_class(IMPORT_OT_SCENE_p3d)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


if __name__ == "__main__":
    register()
