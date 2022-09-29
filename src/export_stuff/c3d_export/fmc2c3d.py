# %%
# import sys
import copy
import c3d
import numpy as np

import sys
from pathlib import Path

import os

print("The current working directory is" + os.getcwd())

# os.chdir(os.path.dirname(os.path.abspath(__file__)))

# for p in sys.path:
#     print(p)

# sys.path.insert(0, Path(__file__).parent.parent.parent)


# for p in sys.path:
#     print(p)

writer = c3d.Writer()
reader = c3d.Reader(open(Path("2014015_C4_05.c3d"), 'rb'))

new_header = c3d.c3d.Header()
new_header.frame_rate = 100.0

writer._header = new_header
writer.set_start_frame(new_header.first_frame)

point_names = np.array([str(i) for i in range(0,52)], dtype=object)

writer.set_point_labels(point_names)

# single blank analog label, otherwise no file creation
writer.set_analog_labels(np.array([''], dtype=object))

gen_scale, analog_scales, analog_offsets = reader.get_analog_transform_parameters()
gen_scale = 1
writer.set_analog_general_scale(gen_scale) 

analog_scales = np.array([])
writer.set_analog_scales(analog_scales)

analog_offsets = np.array([])
writer.set_analog_offsets(analog_offsets)

for i, points, analog in reader.read_frames():
    # print('frame {}: point {}, analog {}'.format(i, points.shape, analog.shape))
    writer.add_frames((points,np.array([[]]) ))

with open(Path("random-points.c3d"), 'wb') as h:
    writer.write(h)


# %%


# if __name__ == "__main__":
# read in .trc file


import re
from collections import defaultdict



def parse_trc(trc_path):
    points_by_frame = defaultdict(lambda: {})

    line_number =0
    with open(Path(trc_path)) as trc:
        for line in trc:
            parsed_line = re.split(r'\t', line)
            # print(line_number)
            # print(parsed_line)

            # header parameters
            if line_number == 2:
                frame_rate = parsed_line[1]
                frame_count = parsed_line[2]
            
            # variable names
            if line_number == 3 :
                drop = ['', 'Time', 'Frame#', '\n']
                point_names = [var for var in parsed_line if var not in drop]

            # actual X,Y,Z coordinates
            if line_number >= 6:
                # construct a list of coordinates for each of the points
                frame_number = parsed_line[0]

                # skip the frame number and time
                xyz_start = 2
                for point in point_names:
                    points_by_frame[frame_number][point] = parsed_line[xyz_start:xyz_start+3]
                    xyz_start+=3

            line_number+=1
    # print(f"Frame Rate: {frame_rate}")
    # print(f"Point Names: {point_names}")

    return frame_rate, point_names, points_by_frame
# %%
# return frame_rate, point_names
trc_sample_path = r"C:\Users\Mac Prible\repos\freemocap\src\export_stuff\c3d_export\dao_yin_interpolated.trc"
frame_rate, point_names, points_by_frame = parse_trc(trc_sample_path)


# %%
writer = c3d.Writer()
reader = c3d.Reader(open(Path("2014015_C4_05.c3d"), 'rb'))

new_header = c3d.c3d.Header()
new_header.frame_rate = 100.0

writer._header = new_header
writer.set_start_frame(new_header.first_frame)

point_names = np.array([str(i) for i in range(0,52)], dtype=object)

writer.set_point_labels(point_names)

# single blank analog label, otherwise no file creation
writer.set_analog_labels(np.array([''], dtype=object))

gen_scale, analog_scales, analog_offsets = reader.get_analog_transform_parameters()
gen_scale = 1
writer.set_analog_general_scale(gen_scale) 

analog_scales = np.array([])
writer.set_analog_scales(analog_scales)

analog_offsets = np.array([])
writer.set_analog_offsets(analog_offsets)

for i, points, analog in reader.read_frames():
    # print('frame {}: point {}, analog {}'.format(i, points.shape, analog.shape))
    writer.add_frames((points,np.array([[]]) ))

with open(Path("random-points.c3d"), 'wb') as h:
    writer.write(h)



# %% 