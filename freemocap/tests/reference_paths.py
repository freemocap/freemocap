"""Allow reference tests to use isolated data without changing normal defaults."""

import os
from pathlib import Path


def recordings_root() -> Path:
    return Path(os.environ.get(
        "FREEMOCAP_REFERENCE_RECORDINGS_ROOT", Path.home() / "freemocap_data/recordings",
    ))


def prepared_root() -> Path:
    return Path(os.environ.get(
        "FREEMOCAP_PROVENANCE_PREPARED_ROOT", Path.home() / "freemocap_data/testing/prepared",
    ))
