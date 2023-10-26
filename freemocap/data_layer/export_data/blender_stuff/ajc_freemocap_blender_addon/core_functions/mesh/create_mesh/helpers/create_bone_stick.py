import bmesh
import bpy


def create_bone_mesh(child_empty: bpy.types.Object,
                     parent_name: str,
                     parent_empty: bpy.types.Object,
                     skin_radius: float = .005,
                     ):
    bone_name = f"{parent_name}_bone_mesh"
    stick_mesh = bpy.data.meshes.new(name=bone_name)
    mesh_obj = bpy.data.objects.new(bone_name, stick_mesh)
    mesh_obj.location = parent_empty.location
    bpy.context.collection.objects.link(mesh_obj)

    bm = bmesh.new()

    parent_vertex = bm.verts.new(parent_empty.location)
    child_vertex = bm.verts.new(child_empty.location)

    bm.edges.new([parent_vertex, child_vertex])

    bm.to_mesh(stick_mesh)
    bm.free()

    modifier = mesh_obj.modifiers.new(name="Skin", type='SKIN')
    modifier.use_smooth_shade = True

    for vertex in stick_mesh.skin_vertices[0].data:
        vertex.radius = skin_radius, skin_radius

    return mesh_obj
