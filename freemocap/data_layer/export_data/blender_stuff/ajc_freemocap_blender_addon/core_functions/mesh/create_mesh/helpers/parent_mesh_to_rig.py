import logging
import bpy
logger = logging.getLogger(__name__)
def parent_mesh_to_rig(meshes, rig):
    logger.info("Parenting mesh to rig...")
    try:
        meshes[0].name = "mesh"
        # Deselect all
        bpy.ops.object.select_all(action='DESELECT')
        # Select all body meshes
        for body_mesh in meshes:
            body_mesh.select_set(True)
        # Set fmc_mesh as active
        bpy.context.view_layer.objects.active = meshes[0]
        # Join the body meshes
        bpy.ops.object.join()
        ### Parent the fmc_mesh with the rig
        # Select the rig
        rig.select_set(True)
        # Set rig as active
        bpy.context.view_layer.objects.active = rig
        # Parent the mesh and the rig with automatic weights
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    except Exception as e:
        logger.error(f"Failed to parent mesh to rig: {e}")
        raise e
