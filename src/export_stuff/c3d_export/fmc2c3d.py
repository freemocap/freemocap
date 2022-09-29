# %%
# import sys
import copy
import c3d
import numpy as np

import sys
from pathlib import Path

import os

print("The current working directory is" + os.getcwd())

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# for p in sys.path:
#     print(p)

# sys.path.insert(0, Path(__file__).parent.parent.parent)


# for p in sys.path:
#     print(p)

writer = c3d.Writer()
reader = c3d.Reader(open(Path(Path(__file__).parent, "2014015_C4_05.c3d"), 'rb'))
# Reformat header events
# writer._header.encode_events(writer._header.events)




### BUILD NEW HEADER FROM SCRATCH ####
new_header = c3d.c3d.Header()

new_header.parameter_block = 2
new_header.data_block = 11
new_header.point_count = 52
new_header.analog_count = 0
new_header.first_frame = 1
new_header.last_frame = 195
new_header.analog_per_frame = 15
new_header.frame_rate = 100.0
new_header.max_gap = 10
# new_header.scale_factor = -0.10000000149011612
new_header.scale_factor = -0.10000000149011612

new_header.long_event_labels = True
new_header.event_count = 0
new_header.event_block = b''
new_header.event_timings = np.zeros(0, dtype=np.float32)
new_header.event_disp_flags = np.zeros(0, dtype=np.bool)
new_header.event_labels = []
#####################################

# new_header = copy.deepcopy(reader._header)


writer._header = new_header
# writer._header = copy.deepcopy(reader._header)

# Transfer a minimal set parameters
writer.set_start_frame(reader.first_frame)
writer.set_point_labels(reader.point_labels)
writer.set_analog_labels(reader.analog_labels)

gen_scale, analog_scales, analog_offsets = reader.get_analog_transform_parameters()
writer.set_analog_general_scale(gen_scale) # gen_scale = 1
writer.set_analog_scales(analog_scales) 
writer.set_analog_offsets(analog_offsets)

for i, points, analog in reader.read_frames():
    # print('frame {}: point {}, analog {}'.format(i, points.shape, analog.shape))
    writer.add_frames((points, analog))

with open(Path(Path(__file__).parent,"random-points.c3d"), 'wb') as h:
    writer.write(h)


# %%


# if __name__ == "__main__":
