import json
import logging
import pickle
from pathlib import Path
from typing import Union, TYPE_CHECKING

import numpy as np

logger = logging.getLogger(__name__)

# this allows us to import the `FreemocapDataHandler` class for type hinting without causing a circular import
if TYPE_CHECKING:
    from ajc_freemocap_blender_addon.core_functions.freemocap_data_handler.handler import \
        FreemocapDataHandler


class FreemocapDataSaver:
    def __init__(self, handler: "FreemocapDataHandler"):
        self.handler = handler

    def save(self, recording_path: str):
        recording_path = Path(recording_path)
        try:
            save_path = Path(recording_path) / "saved_data"
            save_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Saving freemocap data to {save_path}")

            self._save_data_readme(save_path=save_path)

            self._save_info(save_path)

            self._save_npy(save_path)
            self._save_csv(save_path)

            logger.success(f"Saved freemocap data to {save_path}")

        except Exception as e:
            logger.error(f"Failed to save data to disk: {e}")
            logger.exception(e)
            raise e

    def _save_csv(self, save_path: Union[str, Path]):
        """
        Save the data as csv files (use `np` methods to save the data so it will work without pandas (aka, it will run in Blender w/o extra dependencies)
        :param save_path:
        :return:
        """
        csv_path = Path(save_path) / "csv"
        csv_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Saving csv files to {csv_path}")

        components = {
            'body': self.handler.body_frame_name_xyz,
            'right_hand': self.handler.right_hand_frame_name_xyz,
            'left_hand': self.handler.left_hand_frame_name_xyz,
            'face': self.handler.face_frame_name_xyz
        }

        for name, other_component in self.handler.freemocap_data.other.items():
            components[name] = other_component.data

        all_csv_header = ""

        for component_name, component_data in components.items():
            csv_header = "".join(
                [f"{name}_x, {name}_y, {name}_z," for name in
                 self.handler.get_trajectory_names(component_name=component_name)])
            all_csv_header += csv_header

            reshaped_data = component_data.reshape(component_data.shape[0], -1)
            np.savetxt(str(csv_path / f"{component_name}_trajectories.csv"), reshaped_data, delimiter=",",
                       fmt='%s', header=csv_header)
            logger.debug(
                f"Saved {component_name}_frame_name_xyz to {csv_path / f'{component_name}_frame_name_xyz.csv'}")

        np.savetxt(str(save_path / "all_trajectories.csv"),
                   self.handler.all_frame_name_xyz.reshape(self.handler.all_frame_name_xyz.shape[0], -1), delimiter=",",
                   fmt='%s', header=all_csv_header)
        logger.debug(f"Saved all_frame_name_xyz to {save_path / 'all_trajectories.csv'}")

    def _save_npy(self, save_path: Union[str, Path]):
        npy_path = Path(save_path) / "npy"
        npy_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Saving npy files to {npy_path}")

        np.save(str(npy_path / "body_frame_name_xyz.npy"), self.handler.body_frame_name_xyz)
        logger.debug(f"Saved body_frame_name_xyz to {npy_path / 'body_frame_name_xyz.npy'}")

        np.save(str(npy_path / "right_hand_frame_name_xyz.npy"), self.handler.right_hand_frame_name_xyz)
        logger.debug(f"Saved right_hand_frame_name_xyz to {npy_path / 'right_hand_frame_name_xyz.npy'}")

        np.save(str(npy_path / "left_hand_frame_name_xyz.npy"), self.handler.left_hand_frame_name_xyz)
        logger.debug(f"Saved left_hand_frame_name_xyz to {npy_path / 'left_hand_frame_name_xyz.npy'}")

        np.save(str(npy_path / "face_frame_name_xyz.npy"), self.handler.face_frame_name_xyz)
        logger.debug(f"Saved face_frame_name_xyz to {npy_path / 'face_frame_name_xyz.npy'}")

        for name, component in self.handler.freemocap_data.other.items():
            np.save(str(npy_path / f"{name}_frame_name_xyz.npy"), component.data)
            logger.debug(f"Saved {name}_frame_name_xyz to {npy_path / f'{name}_frame_name_xyz.npy'}")

        np.save(str(npy_path / "all_frame_name_xyz.npy"), self.handler.all_frame_name_xyz)
        logger.debug(f"Saved all_frame_name_xyz to {npy_path / 'all_frame_name_xyz.npy'}")

    def _save_data_readme(self, save_path: Union[str, Path]):
        logger.info(f"Saving data readme to {save_path}")
        readme_path = Path(save_path) / "_FREEMOCAP_DATA_README.md"
        readme_path.write_text(DATA_README_TEXT, encoding="utf-8")

    def _save_pickle(self, path: Union[str, Path]):

        pickle_path = Path(path) / "freemocap_data_handler.pkl"
        logger.info(f"Saving `FreemocapDataHandler` pickle to {pickle_path}")
        with open(str(pickle_path), "wb") as f:
            pickle.dump(self.handler, f)

    def _save_info(self, save_path: Union[str, Path]):
        info_path = Path(save_path) / "info"
        info_path.mkdir(parents=True, exist_ok=True)
        self._save_pickle(info_path)
        self._save_trajectory_names(info_path)
        self.save_metadata(info_path)

    def save_metadata(self, path: Union[str, Path]):
        metadata_path = Path(path) / "metadata.json"
        metadata = self.handler.metadata
        metadata_path.write_text(json.dumps(metadata, indent=4))
        logger.debug(f"Saved metadata to {metadata_path}")

    def _save_trajectory_names(self, path: Union[str, Path]):
        # save trajectory names
        trajectory_names_path = Path(path) / "trajectory_names.json"
        trajectory_names = {
            "body": self.handler.body_names,
            "right_hand": self.handler.right_hand_names,
            "left_hand": self.handler.left_hand_names,
            "face": self.handler.face_names,
            "other": {key: value.trajectory_names for key, value in
                      self.handler.freemocap_data.other.items()}
        }
        trajectory_names_path.write_text(json.dumps(trajectory_names, indent=4))
        logger.debug(f"Saved trajectory names to {trajectory_names_path}")


DATA_README_TEXT = """
# Freemocap Data
This folder contains the data extracted from the recording.
## Data
The data is stored in the following files:
### `trajectory_names.json`
A json file containing the names of the trajectories in the data. 
The order of the trajectories is the same as the order of the data in the npy files, and was used to make the headers in the .csv files.

The format is as follows:
```json
{{
"body": ["nose", "left_eye", "right_eye", ...],
    "hands": {"right": ["wrist", "thumb", "index", ...], "left": ["wrist", "thumb", "index", ...]},
    "face": ["nose", "left_eye", "right_eye", ...],
    "other": {"other_component_name": ["trajectory_name_1", "trajectory_name_2", ...]}
}}
```
### `freemocap_data_hanlder.pkl`
This is a 'pickle' file containing the `FreeMocapDataHandler` object. This object contains all of the data in the other files, and is an ease way to access the data in python.

To load it, you can do:
```python
import pickle
with open("freemocap_data_handler.pkl", "rb") as f:
    handler = pickle.load(f)
print(freemocap_data_handler)
```
The resulting object is a `FreeMocapDataHandler` object - check the class definition for more information on how to use it.


### `/npy` folder
- `body_frame_name_xyz.npy`: Body trajectory data in the format, dimensions: (frame, trajectory_name, xyz)
- `right_hand_frame_name_xyz.npy`: Right hand trajectory data in the format, dimensions: (frame, trajectory_name, xyz)
- `left_hand_frame_name_xyz.npy`: Left hand trajectory data in the format, dimensions: (frame, trajectory_name, xyz)
- `face_frame_name_xyz.npy`: Face trajectory data in the format, dimensions: (frame, trajectory_name, xyz)
- `other_frame_name_xyz.npy`: Other component trajectory data in the format, dimensions: (frame, trajectory_name, xyz)
- `all_frame_name_xyz.npy`: All trajectory data in the format, dimensions: (frame, trajectory_name, xyz)

Numpy arrays containing the trajectory data. Note that the data is stored in the format (frame, trajectory_name, xyz).
Numpy arrays are stored in binary format - this means that they are not human-readable, but they are much faster to load and manipulate.

All of these files share a common format - they are three-dimensional arrays with the following dimensions:
- `frame`: The frame number
- `name`: The index of the name of this trajectory (e.g. `head`, `left_hand_index`, etc.) in the relevant entry `trajectory_names.json` file. (i.e. for `mediapipe` data, the 'nose' trajectory is the 0th entry in the list under `body` key). For `all_frame_name_xyz.npy`, this is the index of the trajectory name in the list of all trajectory names concatenated together. 
- `xyz`: The x, y, and z coordinates of the trajectory at the given frame number (x = 0, y = 1, z = 2)

To access a specific data point, you can think of the name (`..._frame_name_xyz`) as an 'address' for where the point lives in the 3d matrix.

You can also use the `trajectory_names.json` data as a look up table to find the index of a trajectory name.

```python
import json
trajectory_names = json.load("trajectory_names.json")
nose_index = trajectory_names["body"].index("nose") # `nose_index == 0` in mediapipe data
nose_xyz = body_frame_name_xyz[100, nose_index, :] # data from the 100th frame, of the `nose_index`th trajectory, all (:) dimensions (x, y, z)

nose_y = np.load("body_frame_name_xyz.npy")[100, nose_index, 1] # data from the 100th frame, of the nose trajectory, at the 1st dimension (y)
```

### `/csv` folder
- `body_frame_name_xyz.csv`: Body trajectory data in the `csv` format
- `right_hand_frame_name_xyz.csv`: Right hand trajectory data in the `csv` format
- `left_hand_frame_name_xyz.csv`: Left hand trajectory data in the `csv` format
- `face_frame_name_xyz.csv`: Face trajectory data in the `csv` format
- `other_frame_name_xyz.csv`: Other component trajectory data in the `csv` format
- `all_frame_name_xyz.csv`: All trajectory data in the `csv` format

The header of each file is the list of trajectory names, with each marker's x, y, and z coordinates as a separate column (format: `[name]_x`, `[name]_y`, `[name]_z`).                 
"""
