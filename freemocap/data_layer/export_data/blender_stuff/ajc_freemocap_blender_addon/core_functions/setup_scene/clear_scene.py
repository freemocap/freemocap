import bpy


def clear_scene():
    ###%% clear the scene - Scorch the earth \o/
    print("Clearing scene...")
    try:
        bpy.ops.object.mode_set(mode="OBJECT")
    except:
        pass
    try:
        bpy.ops.object.select_all(action="SELECT")  # select all objects
        bpy.ops.object.delete(use_global=True)  # delete all objects from all scenes
        bpy.ops.outliner.orphans_purge(num_deleted=2224, do_local_ids=True, do_linked_ids=True, do_recursive=True)
    except:
        pass
