import bpy
import numpy as np

print("loading gaze data as empties")

path_to_sleap_xyz_npy_path = r"C:\Users\jonma\Dropbox\FreeMoCapProject\FreeMocap_Data\sesh_2022-05-07_17_15_05_pupil_wobble_juggle_0\DataArrays\sleap_3d_points.npy"
sleap_fr_mar_xyz = np.load(path_to_sleap_xyz_npy_path)


print(f'shape of sleap_fr_mar_xyz: {sleap_fr_mar_xyz.shape}')

sleap_fr_mar_x = sleap_fr_mar_xyz[:,:,0]*.001
sleap_fr_mar_y = sleap_fr_mar_xyz[:,:,1]*.001
sleap_fr_mar_z = sleap_fr_mar_xyz[:,:,2]*.001

#%%
print(f'loading sleap_data...')


for this_sleap_track_num in  range(sleap_fr_mar_xyz.shape[1]):
    bpy.ops.object.empty_add(type='PLAIN_AXES')
    this_empty = bpy.context.active_object
    print(this_empty)
    for frame_num in range(sleap_fr_mar_xyz.shape[0]):
        if frame_num % 100 == 0:
            print(f'frame {frame_num}')

        this_empty.location = (sleap_fr_mar_x[frame_num, this_sleap_track_num],
                               sleap_fr_mar_y[frame_num, this_sleap_track_num],
                               sleap_fr_mar_z[frame_num, this_sleap_track_num])
        this_empty.scale = (0.1, 0.1, .01)
        
        # this_empty.name = 'right_eye_gaze'
        bpy.context.view_layer.update()
        this_empty.keyframe_insert(data_path='location',frame=frame_num)

print('done!') 