from typing import Union
import papermill as pm
from pathlib import Path



def generate_jupyter_notebook(path_to_recording:Union[str,Path]):
    path_to_this_directory = Path(__file__).parent/ 'freemocap_data_visuals_template.ipynb'
    path_to_output_notebook = Path(path_to_recording) / 'freemocap_data_visualizations.ipynb'

    return pm.execute_notebook(
        input_path = path_to_this_directory,
        output_path = path_to_output_notebook,
        parameters=dict(path_to_recording= path_to_recording)
    )   

if __name__ == '__main__':
    path_to_recording = r'C:\Users\aaron\FreeMocap_Data\recording_sessions\recording_15_19_00_gmt-4__brit_baseline'
    generate_jupyter_notebook(path_to_recording)
