import papermill as pm
from pathlib import Path


def generate_jupyter_notebook(path_to_recording:Path):
    path_to_this_directory = Path(__file__).parent

    res = pm.execute_notebook(
        input_path = path_to_this_directory / 'freemocap_data_visuals_template.ipynb',
        output_path = path_to_recording / 'freemocap_data_visualizations.ipynb',
        parameters=dict(path_to_recording= str(path_to_recording))
    )   


if __name__ == '__main__':
    path_to_recording= Path(r'D:\2023-05-10_session_aaron_michael_jon_milo\1.0_recordings\calibration_one\sesh_2023-05-10_16_39_27_JSM_fun_walk')
    generate_jupyter_notebook(path_to_recording)
