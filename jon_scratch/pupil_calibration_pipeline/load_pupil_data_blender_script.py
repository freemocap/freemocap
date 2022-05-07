import bpy
import numpy as np

print("loading gaze data as empties")

path_to_right_eye_gaze_xyz_npy = r"C:\Users\jonma\Dropbox\FreeMoCapProject\FreeMocap_Data\sesh_2022-02-15_11_54_28_pupil_maybe\DataArrays\right_eye_gaze_fr_xyz.npy"
r_gaze_eye_in_head_xyz = np.load(path_to_right_eye_gaze_xyz_npy)

r_gaze_eye_in_head_x = r_gaze_eye_in_head_xyz[:,0]*.001
r_gaze_eye_in_head_y = r_gaze_eye_in_head_xyz[:,1]*.001
r_gaze_eye_in_head_z = r_gaze_eye_in_head_xyz[:,2]*.001

# #%%
# %matplotlib
# plt.plot(r_eye_norm_pos_x, '.')
#%%
print(f'loading right_eye_data...')
bpy.ops.object.empty_add(type='SPHERE')
this_empty = bpy.context.active_object
# this_empty.name = 'right_eye_gaze'

for frame_num in range(r_gaze_eye_in_head_xyz.shape[0]):
    if frame_num % 100 == 0:
        print(f'frame {frame_num}')

    this_empty.location = (r_gaze_eye_in_head_x[frame_num],
                          r_gaze_eye_in_head_y[frame_num],
                          r_gaze_eye_in_head_z[frame_num])
    this_empty.scale = (0.01, 0.01, 0.01)
    
    this_empty.name = 'right_eye_gaze'
    
    this_empty.keyframe_insert(data_path='location',frame=frame_num)





path_to_left_eye_gaze_xyz_npy = r"C:\Users\jonma\Dropbox\FreeMoCapProject\FreeMocap_Data\sesh_2022-02-15_11_54_28_pupil_maybe\DataArrays\left_eye_gaze_fr_xyz.npy"
l_gaze_eye_in_head_xyz = np.load(path_to_left_eye_gaze_xyz_npy)

l_gaze_eye_in_head_x = l_gaze_eye_in_head_xyz[:,0]*.001
l_gaze_eye_in_head_y = l_gaze_eye_in_head_xyz[:,1]*.001
l_gaze_eye_in_head_z = l_gaze_eye_in_head_xyz[:,2]*.001

aprint(f'loading left_eye_data...')
bpy.ops.object.empty_add(type='SPHERE')
this_empty = bpy.context.active_object
# this_empty.name = 'right_eye_gaze'

for frame_num in range(l_gaze_eye_in_head_xyz.shape[0]):
    if frame_num % 100 == 0:
        print(f'frame {frame_num}')

    this_empty.location = (l_gaze_eye_in_head_x[frame_num],
                          l_gaze_eye_in_head_y[frame_num],
                          l_gaze_eye_in_head_z[frame_num])
    this_empty.scale = (0.01, 0.01, 0.01)

    this_empty.name = 'left_eye_gaze'
        
    this_empty.keyframe_insert(data_path='location',frame=frame_num)







print('done!') 