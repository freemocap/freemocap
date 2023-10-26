from typing import Union, List

import numpy as np

from ajc_freemocap_blender_addon.core_functions.mesh.create_mesh.helpers.create_material import create_material

import bpy


def put_sphere_mesh_at_location(
    name: str,
    location: List[float],
    sphere_scale: float = 0.02,
    material: Union[bpy.types.Material, str] = None,
    color: str = "#00FFFF",
    marker_type: str = "generic",
    emission_strength: float = 1.0):

    if not len(location) == 3:
        raise ValueError(f"location must be a list of length 3, not {len(location)}")
    # If material is None, create a default material
    if material is None:
        material = create_material(
            color=color,
            name=marker_type,
            emission_strength=emission_strength,
        )

    # Ensure the provided material is a bpy.types.Material object
    assert isinstance(material, bpy.types.Material), "Material must be a bpy.types.Material object or a color string"

    bpy.ops.mesh.primitive_uv_sphere_add(segments=8,
                                         ring_count=8,
                                         scale=(sphere_scale, sphere_scale, sphere_scale),
                                         location=location,
                                         align='WORLD',
                                         enter_editmode=False,)
    sphere = bpy.context.editable_objects[-1]
    sphere.name = f"{name}_joint_mesh"
    sphere.data.materials.append(material)
    return sphere
