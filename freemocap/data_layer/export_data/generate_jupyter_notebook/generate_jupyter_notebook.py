import logging
import json
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)


def generate_jupyter_notebook(path_to_recording: Union[str, Path]):
    recording_name = Path(path_to_recording).name
    path_to_template_notebook = Path(__file__).parent / "freemocap_template.ipynb"
    path_to_output_notebook = Path(path_to_recording) / f"{recording_name}.ipynb"

    with open(path_to_template_notebook, "r") as file:
        template_notebook = json.load(file)

    template_notebook["cells"][3]["source"] = [f'path_to_recording = "{str(path_to_recording)}"']

    with open(path_to_output_notebook, "w") as file:
        json.dump(template_notebook, file)


if __name__ == "__main__":
    path_to_recording = r"PATH/TO/RECORDING/FOLDER"
    generate_jupyter_notebook(path_to_recording)
