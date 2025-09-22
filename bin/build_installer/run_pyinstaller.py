import logging
import os
from pathlib import Path

import PyInstaller.__main__

logger = logging.getLogger(__name__)

os.environ['PYINSTALLER_NO_CONDA'] = '1'

SPEC_FILE_PATH = str(Path(__file__).parent / 'freemocap.spec')
if not Path(SPEC_FILE_PATH).exists():
    raise FileNotFoundError(f"Spec file not found at {SPEC_FILE_PATH}")


def run_pyinstaller():
    print(f"Running PyInstaller with spec file {SPEC_FILE_PATH}...")

    installer_parameters = [
        # SPEC_FILE_PATH,
        '--log-level', 'INFO'
    ]

    PyInstaller.__main__.run(installer_parameters)


if __name__ == "__main__":
    run_pyinstaller()
