"""Session-wide test setup.

Lives at the test-package root so every test gets it, including ones that never touch
the pipeline fixtures.
"""

import pytest
from skellylogs.handlers.websocket_log_queue_handler import create_websocket_log_queue


@pytest.fixture(scope="session", autouse=True)
def websocket_log_queue() -> None:
    """Create the websocket log queue before any test runs.

    `PipelineIPC.__init__` calls `get_websocket_log_queue()` unconditionally, and that
    raises `ValueError: Websocket log queue not created yet` unless something created it
    first. In the real app `configure_logging()` does that at startup; tests never call it,
    so anything that stands up a pipeline dies on construction.

    Autouse and session-scoped rather than opt-in, because the failure mode is a new test
    file forgetting a fixture it has no reason to know about. The call is idempotent.
    """
    create_websocket_log_queue()
