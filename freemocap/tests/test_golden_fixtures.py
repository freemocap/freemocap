"""The golden fixtures are the wire contract: rebuilding them must reproduce them.

Each fixture is the CBOR encoding of a message built from pinned synthetic values.
If any of these tests fail, something changed the on-the-wire bytes — which is a
CONTRACT CHANGE, not a refactor. Re-run
``freemocap/tests/streaming_fixtures/regenerate_message_golden.py`` deliberately,
then copy the regenerated .bin files into
``freemocap-ui/src/services/server/transport/__fixtures__/`` so both language
sides stay byte-identical.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "streaming_fixtures"
REGENERATOR = FIXTURE_DIR / "regenerate_message_golden.py"


def _load_regenerator():
    spec = importlib.util.spec_from_file_location("regenerate_message_golden", REGENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("filename", [name for name in _load_regenerator().MESSAGES])
def test_rebuilt_message_matches_its_committed_golden_bytes(filename: str) -> None:
    regenerator = _load_regenerator()
    rebuilt: bytes = regenerator.MESSAGES[filename]()
    committed: bytes = (FIXTURE_DIR / filename).read_bytes()
    assert rebuilt == committed, (
        f"{filename} no longer matches the freshly built message - the wire "
        "format changed. This is a contract change: re-run "
        "streaming_fixtures/regenerate_message_golden.py, copy the new .bin "
        "files into freemocap-ui/src/services/server/transport/__fixtures__/, "
        "and update consumers."
    )


def test_python_and_ui_golden_fixtures_are_byte_identical() -> None:
    ui_fixture_dir = (
        Path(__file__).resolve().parents[2]
        / "freemocap-ui"
        / "src"
        / "services"
        / "server"
        / "transport"
        / "__fixtures__"
    )
    if not ui_fixture_dir.is_dir():
        pytest.skip("freemocap-ui checkout not present next to this repo")
    for filename in _load_regenerator().MESSAGES:
        python_bytes = (FIXTURE_DIR / filename).read_bytes()
        ui_path = ui_fixture_dir / filename
        assert ui_path.is_file(), f"missing UI-side golden fixture: {ui_path}"
        assert python_bytes == ui_path.read_bytes(), (
            f"{filename} differs between freemocap and freemocap-ui - the two "
            "sides are drifting apart. Copy the Python fixture over the UI one."
        )
