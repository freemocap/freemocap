from typing import List, Tuple, Union

import bmesh
import bpy
import numpy as np

from ajc_freemocap_blender_addon.core_functions.mesh.create_mesh.helpers.create_material import create_material


def make_cone_mesh(name: str = "cone_mesh",
                   color: str = "#00FFFF",
                   emission_strength: float = 1.0,
                   transmittance: float = 0.0,
                   vertices: int = 8,
                   radius1: float = 0.05,
                   radius2: float = 0.05,
                   depth: float = 1,
                   end_fill_type: str = 'TRIFAN',
                   align: str = 'WORLD',
                   location: tuple = (0, 0, 0),
                   scale: tuple = (1, 1, 1)):
    bpy.context.scene.cursor.location = (0, 0, 0)

    # define cone object
    bpy.ops.mesh.primitive_cone_add(vertices=vertices,
                                    radius1=radius1,
                                    radius2=radius2,
                                    depth=depth,
                                    end_fill_type=end_fill_type,
                                    align=align,
                                    location=location,
                                    scale=scale)

    cone = bpy.context.active_object
    cone.name = name

    material = create_material(name=f"{name}_material",
                               color=color,
                               )

    cone_object = bpy.data.objects[name]
    cone_mesh = cone_object.data
    cone_mesh.materials.append(material)

    # Go into edit mode
    bpy.context.view_layer.objects.active = cone_object
    bpy.ops.object.mode_set(mode='EDIT')

    # Deselect all vertices
    bm = bmesh.from_edit_mesh(cone_mesh)
    bm.select_mode = {'VERT'}
    bpy.ops.mesh.select_all(action='DESELECT')

    bm.verts.ensure_lookup_table()  # This is important to access vertices by index
    # Select the vertex you want to move the cursor to (i.e. center of the cone base)
    for vertex in bm.verts:
        print(vertex.index, vertex.co)
        x = vertex.co.x
        y = vertex.co.y
        z = vertex.co.z
        if np.allclose(x, 0) and np.allclose(y, 0) and z < 0:
            vertex.select = True
            break

    bpy.context.scene.cursor.location = bpy.context.object.matrix_world @ vertex.co

    bpy.ops.object.mode_set(mode='OBJECT')

    bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
    cone.location = (0, 0, 0)
    bpy.context.scene.cursor.location = (0, 0, 0)

    return cone


def make_joint_sphere_mesh(name: str = "joint_sphere_mesh",
                           subdivisions: int = 2,
                           radius: float = 0.1,
                           align: str = 'WORLD',
                           location: tuple = (0, 0, 0),
                           scale: tuple = (1, 1, 1),
                           color: Union[str, Tuple, List, np.ndarray] = "#00FFFF",
                           ):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdivisions,
                                          radius=radius,
                                          align=align,
                                          location=location,
                                          scale=scale)
    object = bpy.context.active_object
    mesh = object.data
    object.name = name

    material = create_material(name=f"{name}_material",
                               color=color,
                               )
    mesh.materials.append(material)

    return object


def make_bone_mesh(name: str = "bone_mesh",
                   joint_color: Union[str, Tuple, List, np.ndarray] = "#aa0055",
                   cone_color: Union[str, Tuple, List, np.ndarray] = "#00FFFF",
                   axis_visible: bool = True,
                   squish_scale: tuple = (.8, 1, 1),
                   length: float = 1,
                   ) -> bpy.types.Object:

    cone = make_cone_mesh(name=f"{name}_cone_mesh",
                          color=cone_color, )

    joint_sphere = make_joint_sphere_mesh(name=f"{name}_joint_sphere_mesh",
                                          color=joint_color, )
    bpy.ops.object.select_all(action='DESELECT')
    cone.select_set(True)
    joint_sphere.select_set(True)
    bpy.context.view_layer.objects.active = cone
    bpy.ops.object.join()
    bone_mesh_object = bpy.context.active_object
    bone_mesh_object.name = name

    if axis_visible:
        bone_mesh_object.show_axis = True

    bone_mesh_object.scale = squish_scale
    bone_mesh_object.scale *= length
    # apply scale
    bpy.ops.object.transform_apply(scale=True)



    return bone_mesh_object


if __name__ == "__main__" or __name__ == "<run_path>":
    bone_mesh = make_bone_mesh(name="bone_mesh")
    bone_mesh.location = (0, 0, 0)
    bone_mesh_small = make_bone_mesh(name="bone_mesh_small",
                                     length=.5)
    bone_mesh_small.location = (-2, 0, 0)
    bone_mesh_large = make_bone_mesh(name="bone_mesh_large",
                                        length=1.5)
    bone_mesh_large.location = (2, 0, 0)