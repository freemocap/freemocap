import bpy


print(" - Starting (alpha) blender megascript - ")


rig_name = "mixamorig"
rig_constraint_dict_of_dicts_og = {
        "Hips": {
            "COPY_LOCATION": "hip_center",
            "STRETCH_TO": "chest_center",
        },
        "Spine1": {
            "STRETCH_TO": "chest_center",
        },
         "RightShoulder": {
            "COPY_LOCATION": "neck_center",
            "STRETCH_TO": "right_shoulder",
        },
         "LeftShoulder": {
            "COPY_LOCATION": "neck_center",
            "STRETCH_TO": "left_shoulder",
        },
        "RightArm": {
            "STRETCH_TO": "right_elbow",
        },
        "LeftArm": {
            "STRETCH_TO": "left_elbow",
        },
        "RightForeArm": {
            "STRETCH_TO": "right_wrist",
        },
        "LeftForeArm": {
            "STRETCH_TO": "left_wrist",
        },
        "RightHand": {
            "STRETCH_TO": "left_hand_wrist",
        },
        "LeftHand": {
            "STRETCH_TO": "right_hand_wrist",
        },
        "Neck": {
            "STRETCH_TO": "head_center",
        },
        "RightUpLeg": {
            "COPY_LOCATION": "right_hip",
            "STRETCH_TO": "right_knee",
        },
        "LeftUpLeg": {
            "COPY_LOCATION": "left_hip",
            "STRETCH_TO": "left_knee",
        },
        "RightLeg": {
            "STRETCH_TO": "right_ankle",
        },
        "LeftLeg": {
            "STRETCH_TO": "left_ankle",
        },
        "RightFoot": {
            "DAMPED_TRACK": "right_foot_index",
        },
        "LeftFoot": {
            "DAMPED_TRACK": "left_foot_index",
        },
        "RightToeBase": {
            "STRETCH_TO": "right_foot_index",
        },
        "LeftToeBase": {
            "STRETCH_TO": "left_foot_index",
        },
        "Head": {
            "COPY_LOCATION": "head_center",
            "DAMPED_TRACK": "head_center",
        },
    }


### Pre-pend `rig_name` or whatever to bone names
rig_constraint_dict_of_dicts  = {}
for key in rig_constraint_dict_of_dicts_og.keys():
    rig_constraint_dict_of_dicts[f"{rig_name}{key}"] = rig_constraint_dict_of_dicts_og[key]

####
#### Constrain bones to empties
####
armature_name  = "Armature"
armature = bpy.data.objects[armature_name]
# loop through dictionary applying  constraints
try:
    bpy.ops.object.mode_set(mode="POSE")
except:
    pass

for this_bone_name, this_bone_dict in rig_constraint_dict_of_dicts.items():
    print(f"---Setting constraints for bone:{this_bone_name}---")

    for (
            this_constraint_name,
            this_constraint_target_empty_name,
    ) in this_bone_dict.items():
        print(
            f"constraint: {this_constraint_name} with target:{this_constraint_target_empty_name}"
        )
        print("grab bone")
        this_bone = armature.pose.bones[this_bone_name]
        print("apply bone")
        this_constraint = this_bone.constraints.new(type=this_constraint_name)
        this_constraint.name = this_constraint_name
        this_constraint.target = bpy.data.objects[
            this_constraint_target_empty_name
        ]  # point constraint at relevant empty object
