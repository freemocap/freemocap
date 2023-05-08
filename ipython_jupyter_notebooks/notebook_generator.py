import papermill as pm
from pathlib import Path


def generate_jupyter_notebook(path_to_recording:Path):
    path_to_this_directory = Path(__file__).parent

    res = pm.execute_notebook(
        input_path = path_to_this_directory / 'timeseries_plotter.ipynb',
        output_path = path_to_recording / 'timeseries_plotter_output.ipynb',
        parameters=dict(path_to_recording= str(path_to_recording))
    )


if __name__ == '__main__':
    path_to_recording= Path(r'D:\2023-05-03_session_aaron_michael_jon\1.0_recordings\recordings_calib_1\sesh_2023-05-03_17_46_22_aaron_michael_jon')
    generate_jupyter_notebook(path_to_recording)
