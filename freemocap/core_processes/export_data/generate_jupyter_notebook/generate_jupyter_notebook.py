import json
import logging
from pathlib import Path
from typing import Union

from freemocap.utilities.download_sample_data import get_sample_data_path

logger = logging.getLogger(__name__)


def generate_jupyter_notebook(path_to_recording: Union[str, Path]):
    path_to_recording = Path(path_to_recording)
    recording_name = Path(path_to_recording).name
    path_to_template_notebook = Path(__file__).parent / "freemocap_template.ipynb"
    path_to_output_notebook = Path(path_to_recording) / f"{recording_name}.ipynb"

    with open(path_to_template_notebook, "r") as file:
        template_notebook = json.load(file)

    template_notebook["cells"][3]["source"] = [f'path_to_recording = "{str(path_to_recording)}"']

    with open(path_to_output_notebook, "w") as file:
        json.dump(template_notebook, file)


if __name__ == "__main__":
    from freemocap.gui.qt.utilities.save_and_load_gui_state import GuiState

    gui_state = GuiState()
    path_to_recording = get_sample_data_path(gui_state=gui_state)
    # path_to_recording = r"PATH/TO/RECORDING/FOLDER" #specify path to a specific recording here (other wise it will just download sample data)

    generate_jupyter_notebook(path_to_recording)
