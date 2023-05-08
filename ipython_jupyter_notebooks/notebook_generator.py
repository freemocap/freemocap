import papermill as pm
from pathlib import Path


def generate_jupyter_notebook(path_to_recording):
    path_to_this_directory = Path(__file__).parent

    res = pm.execute_notebook(
        path_to_this_directory / 'timeseries_plotter.ipynb',
        path_to_this_directory / 'timeseries_plotter_output.ipynb',
        parameters=dict(path_to_session=path_to_recording)
    )


if __name__ == '__main__':
    path_to_recording= r'D:\2023-05-03_session_aaron_michael_jon\1.0_recordings\recordings_calib_1\sesh_2023-05-03_17_46_22_aaron_michael_jon'
    generate_jupyter_notebook(path_to_recording)
