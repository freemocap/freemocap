import numpy as np
import bpy
from mathutils import Vector
import math
import sys
from pathlib import Path

# get arguments
argv = sys.argv
argv = argv[argv.index("--") + 1:] 
 
# get npy session data
input_npy = argv[0]

# get session path
sesh_path = argv[1]

#the path of the npy build data file 
build_data = Path(__file__).parent.resolve() / "build_data.npy"

#3D array holding [[[x, y, z], [x, y, z]], [[x, y, z], [x, y, z]]] 
arr = np.load(input_npy)

# Saved clean frame where all points are visible and not NANs 
markers_list = np.load(build_data)

#a list containing empty objects
order_of_markers = []

#frame rate 
bpy.context.scene.render.fps = 30

#dictionary corresponding to marker numbers and body parts
body_dict = {
    0:"head1", 
    11:"shoulder_L", 
    12:"shoulder_R", 
    13:"elbow_L", 
    14:"elbow_R", 
    23:"hip_L",
    24:"hip_R", 
    25:"knee_L", 
    26:"knee_R",
    27:"ankle_L",
    28:"ankle_R",
    29:"heel_L", 
    30:"heel_R",
    31:"toe_L",
    32:"toe_R" }

#-----------------------------------------------------------------------------------   

# set project unit 
bpy.context.scene.unit_settings.length_unit = 'METERS'
#iterate through arr and create an empty object at that location for each element
for index, col in enumerate(markers_list):
    # parse string float value into floats, create Vector, set position to Vector

    if math.isnan(col[0]):
        col[0] = 0.0
    if math.isnan(col[1]):
        col[1] = 0.0
    if math.isnan(col[2]):
        col[2] = 0.0
    coord = Vector(((float(col[0])*0.001), (float(col[2])*0.001), (float(col[1]))* -0.001))
        
    #empties
    bpy.ops.object.add(type='EMPTY', location=coord)  
    mt = bpy.context.active_object  
    mt.name = "mt_" + str(index)
    if index in body_dict.keys():
        mt.name += "_" + str(body_dict[index])
    order_of_markers.append(mt)
    #link empty to scene
    bpy.context.scene.collection.objects.link( mt )
    #set location 
    mt.location = coord
    #set the display size of the empty
    mt.empty_display_size = 0.02
    
#--------------------------------------------------------------
#Virtual Markers!

# marker relationships:

# - "weight": the weighted average of multiple markers. the virtual_markers[x] contains the 
#list of markers that affect this virtual one. the weights[x] contains their corresponding weights in order.

bpy.ops.object.mode_set(mode='OBJECT', toggle=False)

#Create virtual marker where parameters are the name of the marker, the markers that affect its position, and each of their weights.
def create_marker_weight(name, markers, weighted):
    center = Vector((0, 0, 0))
    weight_iter = 0
    for x in markers:
        center += x.location*weighted[weight_iter]
        weight_iter += 1
    coord = Vector((float(center[0]), float(center[1]), float(center[2])))
    bpy.ops.object.add(type='EMPTY', location=coord)
    mt = bpy.context.active_object  
    mt.name = name
    bpy.context.scene.collection.objects.link( mt )
    mt.location = coord
    mt.empty_display_size = 0.02
    virtual_markers.append(mt)

#Keeping track of virtual marker info using arrays, where each marker is an index in each array
v_relationship = []
virtual_markers = []
surrounding_markers = []
weights = []

#updates data and creates virtual marker
def update_virtual_data(relationship, surrounding, vweights, vname):
    v_relationship.append(relationship)
    surrounding_markers.append(surrounding)
    weights.append(vweights)
    create_marker_weight(vname, surrounding, vweights)
         
#-----------------------------------------------------------------
#Define relationships and create virtual markers

#Neck Base: Halfway between order_of_markers[12] shoulder_L and order_of_markers[12] shoulder_R
l0 = [order_of_markers[12], order_of_markers[11]]
w0 = [0.5, 0.5]
update_virtual_data("weight", l0, w0, "m_neck")

#Waist Base: Halfway between order_of_markers[24] and order_of_markers[23] 
l0 = [order_of_markers[24], order_of_markers[23]]
w0 = [0.5, 0.5]
update_virtual_data("weight", l0, w0, "m_neck")

#Update the location of virtual markers on each frame
def update_virtual_marker(index):
    if(v_relationship[index] is "weight"):
        center = Vector((0, 0, 0))
        weight_iter = 0
        for x in surrounding_markers[index]:
            center += x.location*weights[index][weight_iter]
            weight_iter += 1
        coord = Vector((float(center[0]), float(center[1]), float(center[2])))
    virtual_markers[index].location = coord
    
#-----------------------------------------------------------------------------------
# Bones! 
    
#adds child bone given corresponding parent and empty
#bone tail will appear at the location of empty
def add_child_bone(bone_name, empty1, empty2):
    #Set armature selected
    armature_data.select_set(state=True)
    #Set edit mode
    bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    #Create a new bone
    new_bone = armature_data.data.edit_bones.new(bone_name)
    #Set bone's size
    new_bone.head = (0,0,0)
    new_bone.tail = (0,0.1,0)
    #Set bone's location to wheel
    new_bone.matrix = empty2.matrix_world
    #set location of bone head
    new_bone.head =  empty1.location
    #set location of bone tail
    new_bone.tail = empty2.location
    return new_bone

#Create armature object
armature = bpy.data.armatures.new('Armature')
armature_object = bpy.data.objects.new('Armature', armature)
#Link armature object to our scene
bpy.context.collection.objects.link(armature_object)
#Make armature variable
armature_data = bpy.data.objects[armature_object.name]
#Set armature active
bpy.context.view_layer.objects.active = armature_data
#Set armature selected
armature_data.select_set(state=True)
#Set edit mode
bpy.ops.object.mode_set(mode='EDIT', toggle=False)
#Set bones in front and show axis
armature_data.show_in_front = True
#True to show axis orientation of bones and false to hide it
armature_data.data.show_axes = False

#get armature object
def get_armature():
    for ob in bpy.data.objects:
        if ob.type == 'ARMATURE':
            armature = ob
            break
    return armature

armature = get_armature()

#a list of tuples where each element represents the info for one bone, and 
#the tuple contains the bone name, the marker of the head, and the marker of the tail
list_of_bones_order = [('upper_arm_L', order_of_markers[11], order_of_markers[13]),
        ('upper_arm_R', order_of_markers[12], order_of_markers[14]),
        ('lower_arm_L', order_of_markers[13], order_of_markers[15]),
        ('lower_arm_R', order_of_markers[14], order_of_markers[16]),
        ('upper_leg_L', order_of_markers[23], order_of_markers[25]),
        ('upper_leg_R', order_of_markers[24], order_of_markers[26]),
        ('lower_leg_L', order_of_markers[25], order_of_markers[27]),
        ('lower_leg_R', order_of_markers[26], order_of_markers[28]),
        ('heel_L', order_of_markers[27], order_of_markers[29]),
        ('heel_R', order_of_markers[28], order_of_markers[30]),
        ('foot_L', order_of_markers[29], order_of_markers[31]),
        ('foot_R', order_of_markers[30], order_of_markers[32]),
        ('neck', order_of_markers[0], virtual_markers[0]),
        ('eye_L', order_of_markers[0], order_of_markers[2]),
        ('ear_L', order_of_markers[2], order_of_markers[7]),
        ('eye_R', order_of_markers[0], order_of_markers[5]),
        ('ear_R', order_of_markers[5], order_of_markers[8]),
        ('shoulder_L', virtual_markers[0], order_of_markers[11]),
        ('shoulder_R', virtual_markers[0], order_of_markers[12]),
        ('torso', virtual_markers[1], virtual_markers[0]),
        ('hip_L', virtual_markers[1], order_of_markers[23]),
        ('hip_R', virtual_markers[1], order_of_markers[24]),
        ]
        
#based on marker # from order_of_markers array add bones for hands:
left_hand_offset = 54
left_hand = [('handL0', order_of_markers[0+left_hand_offset], order_of_markers[1+left_hand_offset]),
    ('handL1', order_of_markers[1+left_hand_offset], order_of_markers[2+left_hand_offset]),
    ('handL2', order_of_markers[2+left_hand_offset], order_of_markers[3+left_hand_offset]),
    ('handL3', order_of_markers[3+left_hand_offset], order_of_markers[4+left_hand_offset]),
    ('handL5', order_of_markers[1+left_hand_offset], order_of_markers[5+left_hand_offset]),
    ('handL6', order_of_markers[5+left_hand_offset], order_of_markers[6+left_hand_offset]),
    ('handL7', order_of_markers[6+left_hand_offset], order_of_markers[7+left_hand_offset]),
    ('handL8', order_of_markers[7+left_hand_offset], order_of_markers[8+left_hand_offset]),
    ('handL9', order_of_markers[5+left_hand_offset], order_of_markers[9+left_hand_offset]),
    ('handL10', order_of_markers[9+left_hand_offset], order_of_markers[10+left_hand_offset]),
    ('handL11', order_of_markers[10+left_hand_offset], order_of_markers[11+left_hand_offset]),
    ('handL12', order_of_markers[11+left_hand_offset], order_of_markers[12+left_hand_offset]),
    ('handL13', order_of_markers[9+left_hand_offset], order_of_markers[13+left_hand_offset]),
    ('handL14', order_of_markers[13+left_hand_offset], order_of_markers[14+left_hand_offset]),
    ('handL15', order_of_markers[14+left_hand_offset], order_of_markers[15+left_hand_offset]),
    ('handL16', order_of_markers[15+left_hand_offset], order_of_markers[16+left_hand_offset]),
    ('handL17', order_of_markers[13+left_hand_offset], order_of_markers[0+left_hand_offset]),
    ('handL18', order_of_markers[0+left_hand_offset], order_of_markers[17+left_hand_offset]),
    ('handL19', order_of_markers[17+left_hand_offset], order_of_markers[18+left_hand_offset]),
    ('handL20', order_of_markers[18+left_hand_offset], order_of_markers[19+left_hand_offset]),
    ('wristL', order_of_markers[15], order_of_markers[0+left_hand_offset]),
    ('handL21', order_of_markers[19+left_hand_offset], order_of_markers[20+left_hand_offset]),]
    
right_hand_offset = 33

right_hand = [('handR0', order_of_markers[18], order_of_markers[1+right_hand_offset]),
    ('handR1', order_of_markers[1+right_hand_offset], order_of_markers[2+right_hand_offset]),
    ('handR2', order_of_markers[2+right_hand_offset], order_of_markers[3+right_hand_offset]),
    ('handR3', order_of_markers[3+right_hand_offset], order_of_markers[4+right_hand_offset]),
    ('handR5', order_of_markers[1+right_hand_offset], order_of_markers[5+right_hand_offset]),
    ('handR6', order_of_markers[5+right_hand_offset], order_of_markers[6+right_hand_offset]),
    ('handR7', order_of_markers[6+right_hand_offset], order_of_markers[7+right_hand_offset]),
    ('handR8', order_of_markers[7+right_hand_offset], order_of_markers[8+right_hand_offset]),
    ('handR9', order_of_markers[5+right_hand_offset], order_of_markers[9+right_hand_offset]),
    ('handR10', order_of_markers[9+right_hand_offset], order_of_markers[10+right_hand_offset]),
    ('handR11', order_of_markers[10+right_hand_offset], order_of_markers[11+right_hand_offset]),
    ('handR12', order_of_markers[11+right_hand_offset], order_of_markers[12+right_hand_offset]),
    ('handR13', order_of_markers[9+right_hand_offset], order_of_markers[13+right_hand_offset]),
    ('handR14', order_of_markers[13+right_hand_offset], order_of_markers[14+right_hand_offset]),
    ('handR15', order_of_markers[14+right_hand_offset], order_of_markers[15+right_hand_offset]),
    ('handR16', order_of_markers[15+right_hand_offset], order_of_markers[16+right_hand_offset]),
    ('handR17', order_of_markers[18], order_of_markers[13+right_hand_offset]),
    ('handR18', order_of_markers[18], order_of_markers[17+right_hand_offset]),
    ('handR19', order_of_markers[17+right_hand_offset], order_of_markers[18+right_hand_offset]),
    ('handR20', order_of_markers[18+right_hand_offset], order_of_markers[19+right_hand_offset]),
    ('wristR', order_of_markers[16], order_of_markers[18]),
    ('handR21', order_of_markers[19+right_hand_offset], order_of_markers[20+right_hand_offset]),]

#helper to create armature from list of tuples
def tuple_to_armature(bones):
    for bone_name, bone_head, bone_tail in bones:
        add_child_bone(bone_name, bone_head, bone_tail)
        
#Set armature selected
armature_data.select_set(state=True)
#Set edit mode
bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        
#create all bones for skeleton body and hands
tuple_to_armature(list_of_bones_order)
tuple_to_armature(right_hand)
tuple_to_armature(left_hand)

#parent heads and tails to empties
#use bone constraints 
def parent_to_empties(bone_name, head, tail):
    #enter pose mode
    bpy.ops.object.posemode_toggle()
    marker = armature.data.bones[bone_name]
    #Set marker selected
    marker.select = True
    #Set marker active
    bpy.context.object.data.bones.active = marker
    bone = bpy.context.object.pose.bones[bone_name]
    #Copy Location Pose constraint: makes the bone's head follow the given empty
    bpy.ops.pose.constraint_add(type='COPY_LOCATION')
    bone.constraints["Copy Location"].target = head
    #Stretch To Pose constraint: makes the bone's tail follow the given empty
    #stretches the bones to reach the tail to that empty so head location is not affected
    bpy.ops.pose.constraint_add(type='STRETCH_TO')
    bone.constraints["Stretch To"].target = tail
    #exit pose mode
    bpy.ops.object.posemode_toggle()
    
#set parents of heads and tails for each bone 
def tuple_to_parented(bones):
    for bone_name, bone_head, bone_tail in bones:
        parent_to_empties(bone_name, bone_head, bone_tail)

tuple_to_parented(list_of_bones_order)
tuple_to_parented(right_hand)
tuple_to_parented(left_hand)

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
        coord = Vector(((float(col[0])*0.001), (float(col[2])*0.001), (float(col[1]))* -0.001))
        if len(order_of_markers) > 0:
            empty = order_of_markers[current_marker]
            empty.location = coord
            current_marker += 1 
            for index in range(len(virtual_markers)):
                update_virtual_marker(index)
    
    
    #keyframe bones
    #Goes through each bone
    for editBone in get_armature().data.edit_bones:
        boneName = editBone.name
        poseBone = arm.pose.bones[boneName]
        poseBone.keyframe_insert('rotation_euler', frame=scene.frame_current)
        poseBone.keyframe_insert('location', frame=scene.frame_current)
        poseBone.keyframe_insert('scale', frame=scene.frame_current)

#-----------------------------------------------------------------------------------
#script to create a mesh of the armature 
def CreateMesh():
    obj = get_armature()

    if obj == None:
        print( "No selection" )
    elif obj.type != 'ARMATURE':
        print( "Armature expected" )
    else:
        return processArmature( bpy.context, obj )

#Use armature to create base object
def armToMesh( arm ):
    name = arm.name + "_mesh"
    dataMesh = bpy.data.meshes.new( name + "Data" )
    mesh = bpy.data.objects.new( name, dataMesh )
    mesh.matrix_world = arm.matrix_world.copy()
    return mesh

#Make vertices and faces 
def boneGeometry( l1, l2, x, z, baseSize, l1Size, l2Size, base ):
    x1 = x  * baseSize * l1Size * 0.8
    z1 = z  * baseSize * l2Size * 0.8
    
    x2 = Vector( (0, 0, 0) )
    z2 = Vector( (0, 0, 0) )

    verts = [
        l1 - x1 + z1,
        l1 + x1 + z1,
        l1 - x1 - z1,
        l1 + x1 - z1,
        l2 - x2 + z2,
        l2 + x2 + z2,
        l2 - x2 - z2,
        l2 + x2 - z2
        ] 

    faces = [
        (base+3, base+1, base+0, base+2),
        (base+6, base+4, base+5, base+7),
        (base+4, base+0, base+1, base+5),
        (base+7, base+3, base+2, base+6),
        (base+5, base+1, base+3, base+7),
        (base+6, base+2, base+0, base+4)
        ]

    return verts, faces

#Process the armature, goes through its bones and creates the mesh
def processArmature(context, arm, genVertexGroups = True):
    print("processing armature {0}".format(arm.name))

    #Creates the mesh object
    meshObj = armToMesh( arm )
    context.collection.objects.link( meshObj )

    verts = []
    edges = []
    faces = []
    vertexGroups = {}

    bpy.ops.object.mode_set(mode='EDIT')

    try:
        #Goes through each bone
        for editBone in get_armature().data.edit_bones:
            boneName = editBone.name
            if boneName == "":
                editBone.name = "bone"
                boneName = "bone"
            poseBone = arm.pose.bones[boneName]

            #Gets edit bone informations
            editBoneHead = editBone.head
            editBoneTail = editBone.tail
            editBoneVector = editBoneTail - editBoneHead
            editBoneSize = editBoneVector.dot( editBoneVector )
            editBoneRoll = editBone.roll
            editBoneX = editBone.x_axis
            editBoneZ = editBone.z_axis
            editBoneHeadRadius = editBone.head_radius
            editBoneTailRadius = editBone.tail_radius

            #Creates the mesh data for the bone
            baseIndex = len(verts)
            baseSize = math.sqrt( editBoneSize )
            newVerts, newFaces = boneGeometry( editBoneHead, editBoneTail, editBoneX, editBoneZ, baseSize, editBoneHeadRadius, editBoneTailRadius, baseIndex )
            verts.extend( newVerts )
            faces.extend( newFaces )

            #Creates the weights for the vertex groups
            vertexGroups[boneName] = [(x, 1.0) for x in range(baseIndex, len(verts))]
        #Assigns the geometry to the mesh
        meshObj.data.from_pydata(verts, edges, faces)

    except:
        bpy.ops.object.mode_set(mode='OBJECT')
    else:
        bpy.ops.object.mode_set(mode='OBJECT')
    #Assigns the vertex groups
    if genVertexGroups:
        for name1, vertexGroup in vertexGroups.items():
            groupObject = meshObj.vertex_groups.new(name = name1)
            for (index, weight) in vertexGroup:
                groupObject.add([index], weight, 'REPLACE')

    #Creates the armature modifier
    modifier = meshObj.modifiers.new('ArmatureMod', 'ARMATURE')
    modifier.object = arm
    modifier.use_bone_envelopes = False
    modifier.use_vertex_groups = True

    meshObj.data.update()

    return meshObj

mesh_obob = CreateMesh()

#-----------------------------------------------------------------------------------
# Clean up the mesh by removing duplicate vertices, make sure all faces are quads, etc

checked = set()
for selected_object in bpy.data.objects:
    if selected_object.type != 'MESH':
        continue
    meshdata = selected_object.data
    if meshdata in checked:
        continue
    else:
        checked.add(meshdata)
    bpy.context.view_layer.objects.active = selected_object
    bpy.ops.object.editmode_toggle()
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles()
    bpy.ops.mesh.tris_convert_to_quads()
    bpy.ops.mesh.normals_make_consistent()
    bpy.ops.object.editmode_toggle()
#Set armature active
bpy.context.view_layer.objects.active = armature_data
#Set armature selected
armature_data.select_set(state=True)
#-----------------------------------------------------------------------------------
#function to register custom handler
bpy.app.handlers.frame_change_post.clear()
def register():
    bpy.app.handlers.frame_change_post.append(my_handler)
   
def unregister():
    bpy.app.handlers.frame_change_post.remove(my_handler)
    
register()

scene = bpy.context.scene

bpy.ops.object.mode_set(mode='OBJECT')

#set keyframes for whole animation
for frame in range(scene.frame_start, scene.frame_end):
   scene.frame_set(frame)
   
#Select objects to export
col = bpy.data.collections.get("Collection")
if col:
   for obj in col.objects:
       if "Armature" == obj.name:
            obj.select_set(True)


#Bake the skeletal animation
# ensure that only the armature is selected in Object mode
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='DESELECT')
#Set armature active
bpy.context.view_layer.objects.active = bpy.data.objects[get_armature().name]
#Set armature selected
bpy.data.objects[get_armature().name].select_set(state=True)

#Change to pose mode
bpy.ops.object.mode_set(mode='POSE')

#Bake the animation
bpy.ops.nla.bake(frame_start=scene.frame_start, frame_end=scene.frame_end, only_selected=False, visual_keying=True, clear_constraints=True, use_current_action=False, bake_types={'POSE'})
    
bpy.ops.object.mode_set(mode='OBJECT')

#delete empties
empties = [e for e in bpy.data.objects
        if e.type.startswith('EMPTY')]
        
while empties:
    bpy.data.objects.remove(empties.pop())

order_of_markers = []


#Select objects to export
col = bpy.data.collections.get("Collection")
if col:
   for obj in col.objects:
       if "Armature" in obj.name:
            obj.select_set(True)
       if obj.name == "Cube":
            bpy.data.objects.remove(obj)
            
#save blender file
blend_file_save_path = sesh_path + "skeletal_animation_session.blend"
print('saving .blend file to - ' +  blend_file_save_path)

bpy.ops.wm.save_as_mainfile(filepath= sesh_path + "skeletal_animation_session.blend")

#export FBX
bpy.ops.export_scene.fbx(filepath=sesh_path + "skeletal_animation_session.fbx", path_mode='RELATIVE', bake_anim=True, use_selection=True, object_types={'MESH', 'ARMATURE'}, use_mesh_modifiers = False, add_leaf_bones = False, axis_forward = '-X', axis_up = 'Z', bake_anim_use_all_bones = False, bake_anim_use_nla_strips = False, bake_anim_use_all_actions = False, bake_anim_force_startend_keying = False) 

#export GLTF
bpy.ops.export_scene.gltf(filepath=sesh_path + "skeletal_animation_session.gltf", export_format='GLTF_EMBEDDED', export_selected=True, ui_tab='ANIMATION')

#export USD
bpy.ops.wm.usd_export(filepath=sesh_path + 'skeletal_animation_session.usdc', selected_objects_only=True, export_animation=True)

