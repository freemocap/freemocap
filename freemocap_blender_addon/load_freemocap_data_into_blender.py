import numpy as np
import bpy

from pathlib import Path
import json
from mathutils import Vector

from rich import print, inspect
from rich.progress import track
from rich.console import Console

console = Console()

console.rule()
console.rule()
console.rule("Hello! getting started with FreeMoCap Loading Stuff :D")
console.rule()

# load mediapipe 3d skeleton data

sessionID = "sesh_2021-12-30_13_57_13_cleanish"

freemocap_data_path = Path("C:/Users/jonma/Dropbox/FreeMoCapProject/FreeMocap_Data")
session_path = freemocap_data_path / sessionID
data_path = session_path / "DataArrays"
mediapipe_skel_data_path = data_path / "mediaPipeSkel_3d_smoothed.npy"

console.rule(style="color({})".format("blue"))
console.print("Loading in data from FreeMoCap SessionID: " + sessionID)
console.rule(style="color({})".format("blue"))

mediapipe_skel_fr_mar_dim = np.load(str(mediapipe_skel_data_path))
mediapipe_skel_fr_mar_dim = (
    mediapipe_skel_fr_mar_dim / 1000
)  # convert from mm to meters

(
    number_of_frames,
    number_of_tracked_points,
    number_of_dimensions,
) = mediapipe_skel_fr_mar_dim.shape
# load default mediapipe layout definitions

mediapipe_definitions_json_path = Path(
    r"C:/Users/jonma/Dropbox/GitKrakenRepos/freemocap/freemocap/dev_scratchpad/dev_alpha/default_json_definitions/freemocap_mediapipe_json.json"
)

with open(mediapipe_definitions_json_path) as json_file:
    mediapipe_definitions_dict = json.load(json_file)

tracked_point_names = mediapipe_definitions_dict["body"]["tracked_point_names"]

bpy.ops.object.empty_add(type="ARROWS", location=(0, 0, 0))

# plop empties at origin with names from mediapipe
empty_scale_factor = 0.05

for this_tracked_point_number in range(len(tracked_point_names)):
    bpy.ops.object.add(type="EMPTY")
    this_empty = bpy.context.active_object
    this_empty = bpy.context.active_object
    this_empty.name = tracked_point_names[this_tracked_point_number]
    this_empty.scale = (empty_scale_factor, empty_scale_factor, empty_scale_factor)


bpy.context.scene.unit_settings.length_unit = "METERS"
bpy.ops.object.mode_set(mode="OBJECT")


for frame_number in track(
    range(number_of_frames),
    description="[cyan]Loading tracked point trajectories as keyframed empties...",
    total=mediapipe_skel_fr_mar_dim.shape[0],
):
    bpy.context.scene.frame_set(frame_number)
    for this_empty_name in tracked_point_names:
        this_empty = bpy.data.objects[this_empty_name]
        this_empty.location = (
            mediapipe_skel_fr_mar_dim[
                frame_number, tracked_point_names.webcam_id(this_empty_name), 0
            ],
            mediapipe_skel_fr_mar_dim[
                frame_number, tracked_point_names.webcam_id(this_empty_name), 1
            ],
            mediapipe_skel_fr_mar_dim[
                frame_number, tracked_point_names.webcam_id(this_empty_name), 2
            ],
        )
        this_empty.keyframe_insert(data_path="location", frame=frame_number)


####################
### There are now EMPTIES in the scene!
####################
console.rule(style="color({})".format("magenta"))
console.print("[magenta] Generating Meta Rig \o/")
console.rule(style="color({})".format("magenta"))

bpy.ops.object.armature_human_metarig_add()
metarig = bpy.context.active_object

metarig_scale = 0.85
metarig.scale = (metarig_scale, metarig_scale, metarig_scale)


bpy.ops.pose.rigify_generate()
console.rule(style="color({})".format("magenta"))

console.rule(style="color({})".format("yellow"))
console.print("[yellow] Driving limb FK whosits with empty location data")
console.rule(style="color({})".format("yellow"))


## if not nan
## 1) copy_location - empty -> limb_FK & limb_IK(?)
## 2) set bpy.context.object.pose.bones["upper_arm_parent.L"].IK_FK = 1 (will later set this via reproj error or something)
## 3) add keyframes after each step with bpy.ops.anim.keyframe_insert_button(all=True)
## if nan
## 1) i think just skip? later we can interpolate IK/FK and whatnot
## on first frame
## set all IK stretch to 0
#
# for frame_number in track(range(number_of_frames), description="[yellow]Driving rig FK controllers with empty locations...", total=mediapipe_skel_fr_mar_dim.shape[0] ):
#    bpy.context.scene.frame_set(frame_number)
#    for this_empty_number, this_empty_name in enumerate(tracked_point_names):
#
#        this_point_connections_dict = mediapipe_definitions_dict["body"]['tracked_point_to_rigify_fk_rig_bone_connections'][this_empty_name]
#
#        this_empty_location = Vector(mediapipe_skel_fr_mar_dim[frame_number,this_empty_number,:])
#
#        if this_point_connections_dict:
#            for this_bone_name, this_bone_connection_dict in this_point_connections_dict.items():
#
#                bpy.ops.object.mode_set(mode='EDIT')
#                if this_bone_connection_dict["track_type"] == "bone_tail":
#                    if this_bone_name == "head" or this_bone_name == "toe":
#                        this_bone_obj = bpy.data.objects["rig"].data.bones[this_bone_name]
##                        this_bone_obj.tail = this_empty_location
#                        inspect(this_bone_obj, methods=True)
#                        break
#
#
#
