import numpy as np


class TimestampLogger:
    pass
    # def __init__(self, _camera_id_list: list[str], camera0_id: str = '0'):
    #     self._camera0_id = camera0_id
    #     self._number_of_cameras = len(_camera_id_list)
    #     self._camera_timestamp_dict = {}
    #
    #     for this_cam_id in _camera_id_list:
    #         self._camera_timestamp_dict[this_cam_id] = np.ndarray(0)
    #
    # def update(self, this_webcam_id, new_timestamp):
    #     self._camera_timestamp_dict[this_webcam_id] = np.append(self._camera_timestamp_dict[this_webcam_id],
    #                                                             new_timestamp)
    #
    #     timestamp_array_lengths = [this_timestamp_array.shape[0] for this_timestamp_array in self._camera_timestamp_dict.values()]
    #
    #     if np.sum(np.diff(timestamp_array_lengths)) == 0:  # if timestamp arrays are all the same length
    #         self._update_timestamp_differences_from_camera()
    #
