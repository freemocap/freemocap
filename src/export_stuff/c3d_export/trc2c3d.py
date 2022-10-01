# Primary function: `trc_to_c3d()`
# 
# Inputs: 
#   - filepath to an existing trc file 
#   - target c3d destination
# 
# Effect of function call: creates a c3d at the target destination.
#
# Note: This works on the sample mediapipe output of "interpolated.trc" and then 
# viewing in within Visual3D, but I haven't otherwise tested it.
#
# Author: mprib
 
import numpy as np
from collections import defaultdict
from pathlib import Path

import c3d
import re

def parse_trc_header(trc_filepath):
    """
    Given a path to a .trc file, return the metadata that will be used
    as inputs for creating the .c3d file header. These are the parameters
    displayed on line 3 of the trc file format

    Returns: Frame Rate, Frame Count, Start Frame, Units (string)
    """


    with open(Path(trc_filepath)) as trc:
        line_number =0
        
        for line in trc:
            # trc is tab delimited
            parsed_line = re.split(r'\t', line)

            # header parameters on third row
            if line_number == 2:
                frame_rate = parsed_line[1]
                frame_count = parsed_line[2]
                units = parsed_line[4]
                frame_start = parsed_line[6]
            
            line_number+=1

    return int(frame_rate), int(frame_count), int(frame_start), units
            

def parse_trc_points(trc_filepath):
    """
    Given a path to a .trc, returns: 
    - a list of point names
        - a useful input for a c3d header 
    - a nested dictionary structured as frame:point:XYZ coord
        - used to construct a nested array of [[X, Y, Z, 0, 0], [....]],...]
          for each frame

    These outputs are to be used to create the point trajectories of a trc file
    """

    points_by_frame = defaultdict(lambda: {})

    with open(Path(trc_filepath)) as trc:
        line_number =0
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

                # skip the frame number and timestamp (first two columns)
                xyz_start = 2
                for point in point_names:

                    # take slices of size 3 to get X, Y, Z for each point
                    raw_list = parsed_line[xyz_start:xyz_start+3]

                    # clean up new lines and convert to numeric
                    raw_list = [float(i.replace("\n","")) for i in raw_list]

                    # add in missing zeroes required by c3d, update dictionary
                    raw_list.extend([0,0])
                    points_by_frame[frame_number][point] = raw_list
                    xyz_start+=3

            line_number+=1

    return point_names, points_by_frame


def trc_to_c3d(trc_filepath, c3d_filepath):
    """
    Given a path to a trc file, convert it into a c3d file format and save it out
    to the provide c3d filepath.
    """
    
    # parse out individual components from trc using helper functions
    frame_rate, frame_count, frame_start, units = parse_trc_header(trc_sample_path)
    point_names, points_by_frame = parse_trc_points(trc_sample_path)

    # Initialize writer object and associated metadata
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

    with open(Path(c3d_filepath), 'wb') as h:
        writer.write(h)
# %%
# Test Functionality
if __name__ == "__main__":
    # note this file has a different vertical orientation than v3d, so it will
    # need to be rotated around to view the marker trajectories
    # import sys

    current_folder = Path(__file__).parent
    trc_sample_path = Path(current_folder,"interpolated.trc")
    new_c3d = Path(current_folder,"test_c3d_export.c3d")
    trc_to_c3d(trc_sample_path, new_c3d)
# %%
