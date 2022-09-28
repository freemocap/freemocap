# %%
# import sys
import copy
import c3d

writer = c3d.Writer()
reader = c3d.Reader(open(r'src\export_stuff\c3d_export\2014015_C4_05.c3d', 'rb'))
writer._header = copy.deepcopy(reader._header)
# Reformat header events
# writer._header.encode_events(writer._header.events)

# Transfer a minimal set parameters
writer.set_start_frame(reader.first_frame)
writer.set_point_labels(reader.point_labels)
writer.set_analog_labels(reader.analog_labels)

gen_scale, analog_scales, analog_offsets = reader.get_analog_transform_parameters()
writer.set_analog_general_scale(gen_scale)
writer.set_analog_scales(analog_scales)
writer.set_analog_offsets(analog_offsets)

for i, points, analog in reader.read_frames():
    # print('frame {}: point {}, analog {}'.format(i, points.shape, analog.shape))
    writer.add_frames((points, analog))

with open(r'src\export_stuff\c3d_export\random-points.c3d', 'wb') as h:
    writer.write(h)


# %%


# if __name__ == "__main__":
