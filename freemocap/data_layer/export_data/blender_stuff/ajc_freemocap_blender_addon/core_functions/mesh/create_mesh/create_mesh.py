import logging
from typing import Dict

import bpy

from ajc_freemocap_blender_addon.core_functions.mesh.create_mesh.helpers.parent_mesh_to_rig import parent_mesh_to_rig
from ajc_freemocap_blender_addon.core_functions.mesh.create_mesh.helpers.put_spheres_on_empties import put_spheres_on_empties, \
    put_bone_meshes_on_empties

logger = logging.getLogger(__name__)


def create_mesh(rig: bpy.types.Object,
                empties: Dict[str, bpy.types.Object], ):
    # Change to edit mode
    meshes = put_spheres_on_empties(empties=empties)
    meshes = put_bone_meshes_on_empties(empties=empties)
    # parent_mesh_to_rig(meshes, rig)
