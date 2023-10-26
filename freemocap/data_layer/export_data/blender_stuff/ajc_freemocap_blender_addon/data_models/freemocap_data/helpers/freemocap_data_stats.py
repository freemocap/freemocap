from dataclasses import dataclass

import numpy as np


def calculate_stats(data):
    mean_x = np.nanmean(data[:, :, 0]) if data.size > 0 else np.nan
    mean_y = np.nanmean(data[:, :, 1]) if data.size > 0 else np.nan
    mean_z = np.nanmean(data[:, :, 2]) if data.size > 0 else np.nan

    std_dev_x = np.nanstd(data[:, :, 0]) if data.size > 0 else np.nan
    std_dev_y = np.nanstd(data[:, :, 1]) if data.size > 0 else np.nan
    std_dev_z = np.nanstd(data[:, :, 2]) if data.size > 0 else np.nan

    min_x = np.nanmin(data[:, :, 0]) if data.size > 0 else np.nan
    min_y = np.nanmin(data[:, :, 1]) if data.size > 0 else np.nan
    min_z = np.nanmin(data[:, :, 2]) if data.size > 0 else np.nan

    max_x = np.nanmax(data[:, :, 0]) if data.size > 0 else np.nan
    max_y = np.nanmax(data[:, :, 1]) if data.size > 0 else np.nan
    max_z = np.nanmax(data[:, :, 2]) if data.size > 0 else np.nan

    return {
        'shape': data.shape if data.size > 0 else np.nan,
        'mean': {"x": mean_x, "y": mean_y, "z": mean_z},
        'std_dev': {"x": std_dev_x, "y": std_dev_y, "z": std_dev_z},
        'range': {'x': {'min': min_x, 'max': max_x},
                  'y': {'min': min_y, 'max': max_y},
                  'z': {'min': min_z, 'max': max_z}
                  }
    }


@dataclass
class FreemocapDataStats:
    body_stats: dict
    right_hand_stats: dict
    left_hand_stats: dict
    face_stats: dict

    @classmethod
    def from_freemocap_data(cls, freemocap_data):
        return cls(
            body_stats=calculate_stats(freemocap_data.body.data),
            right_hand_stats=calculate_stats(freemocap_data.hands['right'].data),
            left_hand_stats=calculate_stats(freemocap_data.hands['left'].data),
            face_stats=calculate_stats(freemocap_data.face.data),
        )

    def _format_dict(self, data):
        if isinstance(data, dict):
            return {k: self._format_dict(v) for k, v in data.items()}
        elif isinstance(data, float):
            return "{:.3f}".format(data)
        else:
            return data

    def __str__(self):
        from pprint import pformat
        return pformat(self._format_dict(self.__dict__), indent=4, compact=True)
