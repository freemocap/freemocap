import numpy as np, bpy
from mathutils import Vector
import math
from pathlib import Path
import sys

#the path of the npy file 
argv = sys.argv
argv = argv[argv.index("--") + 1:]  
input_npy = argv[0]

#3D array holding [[[x, y, z], [x, y, z]], [[x, y, z], [x, y, z]]] 
arr = np.load(input_npy) 

#the first frame
markers_list = arr[0]

#a list containing icosphere objects
order_of_icospheres = []

#frame rate 
bpy.context.scene.render.fps = 30

#-----------------------------------------------------------------------------------   

# set project unit 
bpy.context.scene.unit_settings.length_unit = 'MILLIMETERS'
#iterate through arr and create an empty object at that location for each element
for col in markers_list:
    # parse string float value into floats, create Vector, set position to Vector
    if math.isnan(col[0]):
        col[0] = 0.0
    if math.isnan(col[1]):
        col[1] = 0.0
    if math.isnan(col[2]):
        col[2] = 0.0
    coord = Vector(((float(col[0])), (float(col[2])), (float(col[1]))* -1.0))
    #add icosphere
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.01, enter_editmode=False, location=coord)
    sphere = bpy.context.active_object  
    sphere.name = "Sphere"
    order_of_icospheres.append(sphere)
    #link empty to scene
    bpy.context.scene.collection.objects.link( sphere )
    #set location 
    sphere.location = coord
#-----------------------------------------------------------------------------------
# Animate! 
#find number of frames in animation
num_frames = len(arr)

#change start frame of animation
bpy.context.scene.frame_start = 1
#change end frame of animation
bpy.context.scene.frame_end = num_frames - 1

#create a new handler to change empty positions every frame
def my_handler(scene): 
    bpy.ops.object.mode_set(mode='OBJECT')
    #keep track of current_marker
    current_marker = 0
    #find the current frame number
    frame = scene.frame_current
    #get the list of marker points from the current frame
    markers_list = arr[frame]
    #iterate through list of markers in this frame
    for col in markers_list:
        frame = scene.frame_current
        if math.isnan(col[0]):
            col[0] = 0.0
        if math.isnan(col[1]):
            col[1] = 0.0
        if math.isnan(col[2]):
            col[2] = 0.0
        coord = Vector(((float(col[0])), (float(col[2])), (float(col[1]))* -1.0))
        sphere = order_of_icospheres[current_marker] 
        sphere.location = coord
        sphere.keyframe_insert(data_path='location',frame=scene.frame_current)
        current_marker += 1 

#-----------------------------------------------------------------------------------
#function to register custom handler
bpy.app.handlers.frame_change_post.clear()
def register():
    bpy.app.handlers.frame_change_post.append(my_handler)
   
def unregister():
    bpy.app.handlers.frame_change_post.remove(my_handler)
    
bpy.ops.object.mode_set(mode='OBJECT')
    
register()

bpy.ops.object.mode_set(mode='OBJECT')

scene = bpy.context.scene

#set keyframes for whole animation
for frame in range(scene.frame_start, scene.frame_end):
   scene.frame_set(frame)

#set export path
export_path = str(Path(__file__).parent.resolve().parent.resolve() / "/")

#Select objects to export
col = bpy.data.collections.get("Collection")
if col:
   for obj in col.objects:
       if "Sphere" in obj.name:
           obj.select_set(True)

#save blender file
bpy.ops.wm.save_as_mainfile(filepath= export_path + "blender_data.blend")

#export FBX
bpy.ops.export_scene.fbx(filepath=export_path + "exported_animation_from_script.fbx", path_mode='RELATIVE', bake_anim=True, use_selection=True, object_types={'MESH'}, use_mesh_modifiers = False, add_leaf_bones = False, axis_forward = '-X', axis_up = 'Z', bake_anim_use_all_bones = False, bake_anim_use_nla_strips = False, bake_anim_use_all_actions = False, bake_anim_force_startend_keying = False) 

#export GLTF
bpy.ops.export_scene.gltf(filepath=export_path + "exported_animation_from_script.gltf", export_format='GLTF_EMBEDDED', export_selected=True, ui_tab='ANIMATION', export_nla_strips=False)
