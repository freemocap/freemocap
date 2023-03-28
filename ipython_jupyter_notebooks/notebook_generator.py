import papermill as pm
from pathlib import Path

path_to_session = r'C:\Users\aaron\FreeMocap_Data\recording_sessions\session_2023-01-17_15_47_19\15_50_24_gmt-5'

path_to_this_directory = Path().resolve()/'notebook_generator'

res = pm.execute_notebook(
    path_to_this_directory/'timeseries_plotter.ipynb',
    path_to_this_directory/'timeseries_plotter_output.ipynb',
    parameters = dict(path_to_session=path_to_session)
)

f = 2