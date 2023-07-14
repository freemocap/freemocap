import logging
from pathlib import Path
from typing import Union

import papermill as pm

logging.getLogger("papermill").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def generate_jupyter_notebook(path_to_recording: Union[str, Path]):
    recording_name = Path(path_to_recording).name
    path_to_template_notebook = Path(__file__).parent / "freemocap_template.ipynb"
    path_to_output_notebook = Path(path_to_recording) / f"{recording_name}.ipynb"

    logger.info(f"Jupyter notebook generated at {path_to_output_notebook}")
    success = pm.execute_notebook(
        input_path=path_to_template_notebook,
        output_path=path_to_output_notebook,
        parameters=dict(path_to_recording=str(path_to_recording)),
    )


if __name__ == "__main__":
    path_to_recording = r"C:\Users\aaron\FreeMocap_Data\recording_sessions\recording_15_19_00_gmt-4__brit_baseline"
    generate_jupyter_notebook(path_to_recording)
