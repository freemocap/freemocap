import numpy as np
import bpy
from mathutils import Vector
import math
import sys
from pathlib import Path
import csv
from math import degrees

# get arguments
argv = sys.argv
argv = argv[argv.index("--") + 1:] 
 
# get npy session data
input_frames_data_npy = argv[0]

# get session path
sesh_path = argv[1]

#get session ID
sesh_ID = argv[2]

# A clean array of skeleton data where every marker was tracked that we can build off of
clean_skeleton_position_arr = Path(__file__).parent.resolve() / "build_data.npy"

#3D array holding [[[x, y, z], [x, y, z]], [[x, y, z], [x, y, z]]] 
mediapipe_frames_arr = np.load(input_frames_data_npy)

# Saved clean frame where all points are visible and not NANs 
markers_list = np.load(clean_skeleton_position_arr)
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

#create sub-collection of empties
cname = "Empty_Objects"
empty_collection = bpy.data.collections.new(cname)
bpy.data.collections.get("Collection").children.link(empty_collection)
master_collection = bpy.data.collections.get("Collection")


#iterate through arr and create an empty object at that location for each element
for index, col in enumerate(markers_list):
    # parse string float value into floats, create Vector, set position to Vector

    if math.isnan(col[0]):
        col[0] = np.nan
    if math.isnan(col[1]):
        col[1] = np.nan
    if math.isnan(col[2]):
        col[2] = np.nan
    coord = Vector(((float(col[0])*0.001), (float(col[2])*0.001), (float(col[1]))* -0.001))
        
    #empties
    bpy.ops.object.add(type='EMPTY', location=coord)  
    this_empty = bpy.context.active_object  
    this_empty.name = "mt_" + str(index)
    if index in body_dict.keys():
        this_empty.name += "_" + str(body_dict[index])
    order_of_markers.append(this_empty)

    #link this empty to the scene's Empty collection
    empty_collection.objects.link( this_empty )
    #unlink empty from master collection
    master_collection.objects.unlink(this_empty) 
    #set location 
    this_empty.location = coord
    #set the display size of the empty
    this_empty.empty_display_size = 0.02
    
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
    this_empty = bpy.context.active_object  
    this_empty.name = name
    #link this empty to the scene's Empty collection
    empty_collection.objects.link( this_empty )
    #unlink empty from master collection
    master_collection.objects.unlink(this_empty) 
    this_empty.location = coord
    this_empty.empty_display_size = 0.02
    virtual_markers.append(this_empty)

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
update_virtual_data("weight", l0, w0, "mt_neck")

#Waist Base: Halfway between order_of_markers[24] and order_of_markers[23] 
l0 = [order_of_markers[24], order_of_markers[23]]
w0 = [0.5, 0.5]
update_virtual_data("weight", l0, w0, "mt_waist")

#Update the location of virtual markers on each frame
def update_virtual_marker(index):
    if(v_relationship[index] == "weight"):
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
def add_child_bone(bone_name, empty_child, empty_parent):
    #Set armature selected
    armature_data.select_set(state=True)
    #Set edit mode
    bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    #Create a new bone
    new_bone = armature_data.data.edit_bones.new(bone_name)
    #Set bone's size
    new_bone.head = (0,0,0)
    new_bone.tail = (0,0.1,0)
    new_bone.matrix = empty_parent.matrix_world
    #set location of bone head
    new_bone.head =  empty_child.location
    #set location of bone tail
    new_bone.tail = empty_parent.location
    return new_bone

#Create armature object
armature = bpy.data.armatures.new('Armature')
armature.name = "Armature_MediaPipe"
armature_object = bpy.data.objects.new('Armature', armature)
#set name of armature to specify data type (media pipe)
armature_object.name = "Armature_MediaPipe_Object"
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
        if ob.name == 'Armature_MediaPipe_Object':
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
        ('root', virtual_markers[1], virtual_markers[0]),
        ('hip_L', virtual_markers[1], order_of_markers[23]),
        ('hip_R', virtual_markers[1], order_of_markers[24]),
        ]
        
#based on marker # from order_of_markers array add bones for hands:
left_hand_offset = 54
    
left_hand = [('handL0', order_of_markers[0+left_hand_offset], order_of_markers[1+left_hand_offset]),
    ('handL1', order_of_markers[1+left_hand_offset], order_of_markers[2+left_hand_offset]),
    ('handL2', order_of_markers[2+left_hand_offset], order_of_markers[3+left_hand_offset]),
    ('handL3', order_of_markers[3+left_hand_offset], order_of_markers[4+left_hand_offset]),
    ('handL5', order_of_markers[0+left_hand_offset], order_of_markers[5+left_hand_offset]),
    ('handL6', order_of_markers[5+left_hand_offset], order_of_markers[6+left_hand_offset]),
    ('handL7', order_of_markers[6+left_hand_offset], order_of_markers[7+left_hand_offset]),
    ('handL8', order_of_markers[7+left_hand_offset], order_of_markers[8+left_hand_offset]),
    ('handL9', order_of_markers[0+left_hand_offset], order_of_markers[9+left_hand_offset]),
    ('handL10', order_of_markers[9+left_hand_offset], order_of_markers[10+left_hand_offset]),
    ('handL11', order_of_markers[10+left_hand_offset], order_of_markers[11+left_hand_offset]),
    ('handL12', order_of_markers[11+left_hand_offset], order_of_markers[12+left_hand_offset]),
    ('handL13', order_of_markers[0+left_hand_offset], order_of_markers[13+left_hand_offset]),
    ('handL14', order_of_markers[13+left_hand_offset], order_of_markers[14+left_hand_offset]),
    ('handL15', order_of_markers[14+left_hand_offset], order_of_markers[15+left_hand_offset]),
    ('handL16', order_of_markers[15+left_hand_offset], order_of_markers[16+left_hand_offset]),
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
    ('handR5', order_of_markers[18], order_of_markers[5+right_hand_offset]),
    ('handR6', order_of_markers[5+right_hand_offset], order_of_markers[6+right_hand_offset]),
    ('handR7', order_of_markers[6+right_hand_offset], order_of_markers[7+right_hand_offset]),
    ('handR8', order_of_markers[7+right_hand_offset], order_of_markers[8+right_hand_offset]),
    ('handR9', order_of_markers[18], order_of_markers[9+right_hand_offset]),
    ('handR10', order_of_markers[9+right_hand_offset], order_of_markers[10+right_hand_offset]),
    ('handR11', order_of_markers[10+right_hand_offset], order_of_markers[11+right_hand_offset]),
    ('handR12', order_of_markers[11+right_hand_offset], order_of_markers[12+right_hand_offset]),
    ('handR13', order_of_markers[18], order_of_markers[13+right_hand_offset]),
    ('handR14', order_of_markers[13+right_hand_offset], order_of_markers[14+right_hand_offset]),
    ('handR15', order_of_markers[14+right_hand_offset], order_of_markers[15+right_hand_offset]),
    ('handR16', order_of_markers[15+right_hand_offset], order_of_markers[16+right_hand_offset]),
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
num_frames = len(mediapipe_frames_arr)

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
    markers_list = mediapipe_frames_arr[frame]
    #iterate through list of markers in this frame
    for col in markers_list:
        frame = scene.frame_current
        if math.isnan(col[0]) and math.isnan(col[1]) and math.isnan(col[2]):
           #marker was not tracked, pass
           pass
        else:
           #Flip y and z coordinates, and negate y to account for different coordinate system
           coord = Vector(((float(col[0])*0.001), (float(col[2])*0.001), (float(col[1]))* -0.001))
           if len(order_of_markers) > 0:
                empty = order_of_markers[current_marker]
                empty.location = coord
                for index in range(len(virtual_markers)):
                    update_virtual_marker(index)
        current_marker += 1 
    
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

bpy.ops.object.mode_set(mode='EDIT')

arm = get_armature()

#Connected according to: https://google.github.io/mediapipe/solutions/hands.html#hand-landmark-model

arm.data.edit_bones['shoulder_L'].parent = arm.data.edit_bones['root']
arm.data.edit_bones['shoulder_R'].parent = arm.data.edit_bones['root']

arm.data.edit_bones['upper_arm_L'].parent = arm.data.edit_bones['shoulder_L']
arm.data.edit_bones['upper_arm_R'].parent = arm.data.edit_bones['shoulder_R']
arm.data.edit_bones['lower_arm_L'].parent = arm.data.edit_bones['upper_arm_L']
arm.data.edit_bones['lower_arm_R'].parent = arm.data.edit_bones['upper_arm_R']

arm.data.edit_bones['hip_L'].parent = arm.data.edit_bones['root']
arm.data.edit_bones['hip_R'].parent = arm.data.edit_bones['root']
arm.data.edit_bones['upper_leg_L'].parent = arm.data.edit_bones['hip_L']
arm.data.edit_bones['upper_leg_R'].parent = arm.data.edit_bones['hip_R']
arm.data.edit_bones['lower_leg_L'].parent = arm.data.edit_bones['upper_leg_L']
arm.data.edit_bones['lower_leg_R'].parent = arm.data.edit_bones['upper_leg_R']
arm.data.edit_bones['heel_L'].parent = arm.data.edit_bones['lower_leg_L']
arm.data.edit_bones['heel_R'].parent = arm.data.edit_bones['lower_leg_R']
arm.data.edit_bones['foot_L'].parent = arm.data.edit_bones['heel_L']
arm.data.edit_bones['foot_R'].parent = arm.data.edit_bones['heel_R']


arm.data.edit_bones['neck'].parent = arm.data.edit_bones['root']
arm.data.edit_bones['eye_L'].parent = arm.data.edit_bones['neck']
arm.data.edit_bones['eye_R'].parent = arm.data.edit_bones['neck']
arm.data.edit_bones['ear_L'].parent = arm.data.edit_bones['eye_L']
arm.data.edit_bones['ear_R'].parent = arm.data.edit_bones['eye_R']

    
arm.data.edit_bones['wristL'].parent = arm.data.edit_bones['lower_arm_L']
arm.data.edit_bones['wristR'].parent = arm.data.edit_bones['lower_arm_R']

#------------------------------------------------------------------------

arm.data.edit_bones['handR0'].parent = arm.data.edit_bones['wristR']
arm.data.edit_bones['handR1'].parent = arm.data.edit_bones['handR0']
arm.data.edit_bones['handR2'].parent = arm.data.edit_bones['handR1']
arm.data.edit_bones['handR3'].parent = arm.data.edit_bones['handR2']

arm.data.edit_bones['handR5'].parent = arm.data.edit_bones['wristR']
arm.data.edit_bones['handR6'].parent = arm.data.edit_bones['handR5']
arm.data.edit_bones['handR7'].parent = arm.data.edit_bones['handR6']
arm.data.edit_bones['handR8'].parent = arm.data.edit_bones['handR7']

arm.data.edit_bones['handR9'].parent = arm.data.edit_bones['wristR']
arm.data.edit_bones['handR10'].parent = arm.data.edit_bones['handR9']
arm.data.edit_bones['handR11'].parent = arm.data.edit_bones['handR10']
arm.data.edit_bones['handR12'].parent = arm.data.edit_bones['handR11']

arm.data.edit_bones['handR13'].parent = arm.data.edit_bones['wristR']
arm.data.edit_bones['handR14'].parent = arm.data.edit_bones['handR13']
arm.data.edit_bones['handR15'].parent = arm.data.edit_bones['handR14']
arm.data.edit_bones['handR16'].parent = arm.data.edit_bones['handR15']

arm.data.edit_bones['handR18'].parent = arm.data.edit_bones['wristR']
arm.data.edit_bones['handR19'].parent = arm.data.edit_bones['handR18']
arm.data.edit_bones['handR20'].parent = arm.data.edit_bones['handR19']
arm.data.edit_bones['handR21'].parent = arm.data.edit_bones['handR20']

##------------------------------------------------------------------------


arm.data.edit_bones['handL0'].parent = arm.data.edit_bones['wristL']
arm.data.edit_bones['handL1'].parent = arm.data.edit_bones['handL0']
arm.data.edit_bones['handL2'].parent = arm.data.edit_bones['handL1']
arm.data.edit_bones['handL3'].parent = arm.data.edit_bones['handL2']

arm.data.edit_bones['handL5'].parent = arm.data.edit_bones['wristL']
arm.data.edit_bones['handL6'].parent = arm.data.edit_bones['handL5']
arm.data.edit_bones['handL7'].parent = arm.data.edit_bones['handL6']
arm.data.edit_bones['handL8'].parent = arm.data.edit_bones['handL7']

arm.data.edit_bones['handL9'].parent = arm.data.edit_bones['wristL']
arm.data.edit_bones['handL10'].parent = arm.data.edit_bones['handL9']
arm.data.edit_bones['handL11'].parent = arm.data.edit_bones['handL10']
arm.data.edit_bones['handL12'].parent = arm.data.edit_bones['handL11']

arm.data.edit_bones['handL13'].parent = arm.data.edit_bones['wristL']
arm.data.edit_bones['handL14'].parent = arm.data.edit_bones['handL13']
arm.data.edit_bones['handL15'].parent = arm.data.edit_bones['handL14']
arm.data.edit_bones['handL16'].parent = arm.data.edit_bones['handL15']

arm.data.edit_bones['handL18'].parent = arm.data.edit_bones['wristL']
arm.data.edit_bones['handL19'].parent = arm.data.edit_bones['handL18']
arm.data.edit_bones['handL20'].parent = arm.data.edit_bones['handL19']
arm.data.edit_bones['handL21'].parent = arm.data.edit_bones['handL20']

for editBone in get_armature().data.edit_bones:
    # this line is important, when inheriting scale and using the stretch to constraint the bones freak out
    editBone.inherit_scale = 'NONE'


##------------------------------------------------------------------------

#Select objects to export
col = bpy.data.collections.get("Collection")
            
bpy.ops.object.mode_set(mode='OBJECT')

#Run thorugh frames, export a csv file with local bone rotations
# open the file in the write mode
f = open(sesh_path + sesh_ID + '_local_bone_rotations.csv', 'w')

# create the csv writer
writer = csv.writer(f)
writer.writerow(["Frame_number", "Bone name", "X", "Y", "Z"])
for frame in range(scene.frame_start, scene.frame_end):
    scene.frame_set(frame)
    arm = get_armature()
    coords_per_frame = [frame]
    for bone in arm.pose.bones:
        if bone.parent:
            Original_rot = bone.matrix_basis.copy()

            a = bone.matrix.copy()
            b = bone.parent.matrix.copy()

            q1 = a.to_quaternion()

            q2 = b.to_quaternion()

            difQuat = q1.rotation_difference(q2)

            difEuler = difQuat.to_euler()
            mat = difEuler
        else:
            a = bone.matrix.copy()
            q1 = a.to_quaternion()
            mat = q1.to_euler()
        x = degrees(mat.x)
        y = degrees(mat.y)
        z = degrees(mat.z)
        
        if x < 0.0001:
            x = 0.0
        if y < 0.0001:
            y = 0.0
        if z < 0.0001:
            z = 0.0
        coords_per_frame.append(bone.name)
        coords_per_frame.append(x)
        coords_per_frame.append(y)
        coords_per_frame.append(z)
    writer.writerow(coords_per_frame)


bpy.ops.object.mode_set(mode='OBJECT')


#set keyframes for whole animation
for frame in range(scene.frame_start, scene.frame_end):
   scene.frame_set(frame)
   
#Select objects to export
col = bpy.data.collections.get("Collection")
if col:
   for obj in col.objects:
       if "Armature_MediaPipe_Object" == obj.name:
            obj.select_set(True)


#Bake the skeletal animation
# ensure that only the armature is selected in Object mode
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='DESELECT')

empties = [e for e in bpy.data.objects
        if e.type.startswith('EMPTY')]
for e in empties:
    e.select_set(True)
    
    
#Set armature active
bpy.context.view_layer.objects.active = bpy.data.objects[get_armature().name]
#Set armature selected
bpy.data.objects[get_armature().name].select_set(state=True)

#Change to pose mode
bpy.ops.object.mode_set(mode='POSE')

#Bake the animation
bpy.ops.nla.bake(frame_start=scene.frame_start, frame_end=scene.frame_end, only_selected=False, visual_keying=True, clear_constraints=True, use_current_action=False, bake_types={'POSE', 'OBJECT'})
    
bpy.ops.object.mode_set(mode='OBJECT')

#Select objects to export
col = bpy.data.collections.get("Collection")
if col:
   for obj in col.objects:
       if "Armature" in obj.name:
            obj.select_set(True)
       if obj.name == "Cube" or obj.name == "Light" or obj.name == "Camera":
            bpy.data.objects.remove(obj)
 
for e in empties:
    e.select_set(True)
            
#save blender file
bpy.ops.wm.save_as_mainfile(filepath= sesh_path + sesh_ID + '.blend')

#export FBX
bpy.ops.export_scene.fbx(filepath= sesh_path + sesh_ID + '.fbx', path_mode='RELATIVE', bake_anim=True, use_selection=True, object_types={'MESH', 'ARMATURE', 'EMPTY'}, use_mesh_modifiers = False, add_leaf_bones = False, axis_forward = '-X', axis_up = 'Z', bake_anim_use_all_bones = False, bake_anim_use_nla_strips = False, bake_anim_use_all_actions = False, bake_anim_force_startend_keying = False) 

#export GLTF
bpy.ops.export_scene.gltf(filepath=sesh_path + sesh_ID + '.gltf', export_format='GLTF_EMBEDDED', use_selection=True, ui_tab='ANIMATION')

#export USD
bpy.ops.wm.usd_export(filepath=sesh_path + sesh_ID + '.usdc', selected_objects_only=True, export_animation=True)


#--------------------------------------------------------------------------------------------
#Create a panel to display local bone angles in relation to parent bone
class LOCAL_PT_BoneAnglesPanel(bpy.types.Panel):
    bl_label = "Bone Angles Local"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context):
        arm = get_armature()
 
        row = self.layout.row()
        row.label(text='Bone name')
        row.label(text='Degrees X')
        row.label(text='Degrees Y')
        row.label(text='Degrees Z')
        
        for bone in arm.pose.bones:
            row = self.layout.row()
            row.label(text=bone.name)
            if bone.parent:
                Original_rot = bone.matrix_basis.copy()

                a = bone.matrix.copy()
                b = bone.parent.matrix.copy()

                q1 = a.to_quaternion()

                q2 = b.to_quaternion()

                difQuat = q1.rotation_difference(q2)

                difEuler = difQuat.to_euler()
                mat = difEuler
            
            else:
                a = bone.matrix.copy()
                q1 = a.to_quaternion()
                mat = q1.to_euler()
                
            x = mat.x
            y = mat.y
            z = mat.z
                
            if x < 0.0001:
                x = 0.0
            if y < 0.0001:
                y = 0.0
            if z < 0.0001:
                z = 0.0
            row.label(text='X: {:.3}'.format(degrees(x)))
            row.label(text='Y: {:.3}'.format(degrees(y)))
            row.label(text='Z: {:.3}'.format(degrees(z)))
                

bpy.utils.register_class(LOCAL_PT_BoneAnglesPanel)