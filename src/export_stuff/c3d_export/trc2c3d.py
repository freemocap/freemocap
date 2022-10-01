# %%
import numpy as np
from collections import defaultdict

import c3d
from pathlib import Path
import re

def parse_trc_header(trc_filepath):
    """
    from a given .trc file, return the information that will be used
    as inputs for creating the .c3d file header
    """

    line_number =0
    with open(Path(trc_filepath)) as trc:
        for line in trc:
            parsed_line = re.split(r'\t', line)

            # header parameters
            if line_number == 2:
                frame_rate = parsed_line[1]
                frame_count = parsed_line[2]
                units = parsed_line[4]
                frame_start = parsed_line[6]
            
            line_number+=1

    return int(frame_rate), int(frame_count), int(frame_start), units
            

def parse_trc_points(trc_filepath):
    """
    returns: 
    - a list of point names 
    - a nested dictionary structured as frame:point:XYZ coord

    To be used to create the point trajectories of a trc file
    """

    points_by_frame = defaultdict(lambda: {})

    line_number =0
    with open(Path(trc_filepath)) as trc:
        for line in trc:
            parsed_line = re.split(r'\t', line)
            
            # variable names
            if line_number == 3 :   
                drop = ['', 'Time', 'Frame#', '\n']
                point_names = [var for var in parsed_line if var not in drop]

            # actual X,Y,Z coordinates
            if line_number >= 6:
                # construct a list of coordinates for each of the points
                frame_number = parsed_line[0]
                print(frame_number)

                # skip the frame number and time (first two columns)
                xyz_start = 2
                for point in point_names:

                    # take slices of size 3
                    raw_array = parsed_line[xyz_start:xyz_start+3]
                    print(point, raw_array)

                    # clean up new lines and convert to numeric
                    raw_array = [float(i.replace("\n","")) for i in raw_array]
                    # add in missing zeroes required by c3d
                    raw_array.extend([0,0])
                    # print("Raw Arrary Length:" + str(len(raw_array)))
                    points_by_frame[frame_number][point] = raw_array
                    xyz_start+=3

            line_number+=1

    return point_names, points_by_frame

    
# %%
# return frame_rate, point_names
trc_sample_path = r"C:\Users\Mac Prible\repos\freemocap\src\export_stuff\c3d_export\dao_yin_interpolated.trc"
frame_rate, frame_count, frame_start, units = parse_trc_header(trc_sample_path)
point_names, points_by_frame = parse_trc_points(trc_sample_path)

# Use variables from parse function to create new c3d file
# %%
writer = c3d.Writer()
writer._point_units= units

new_header = c3d.c3d.Header()
new_header.frame_rate = frame_rate
new_header.first_frame= frame_start
new_header.last_frame = frame_count - frame_start + 1
new_header.point_count = len(point_names)
writer._header = new_header
writer.set_start_frame(new_header.first_frame)

# convert point names to appropriate format
point_names = np.array(point_names, dtype=object)
writer.set_point_labels(point_names)

# single blank analog label, otherwise no file creation
writer.set_analog_labels(np.array([''], dtype=object))

for frame in points_by_frame.keys():
    frame_points = []

    for point in point_names:
        frame_points.append(points_by_frame[str(frame)][point])

    writer.add_frames((np.array(frame_points, dtype=np.float32), np.array([[]])))

with open(Path("from_trc.c3d"), 'wb') as h:
    writer.write(h)
