import nox
from nox.sessions import Session

# Project requires Python >=3.11
PYTHON_VERSIONS = ["3.11", "3.12"]


@nox.session(python=PYTHON_VERSIONS)
def test(session: Session) -> None:
    """Run the full backend test suite."""
    session.install("-e", ".[dev]")
    session.run("pytest", "freemocap/tests", "-v")


@nox.session(python="3.12")
def test_sync(session: Session) -> None:
    """Run only the frontend/backend sync tests (schema, settings, HTTP, WebSocket)."""
    session.install("-e", ".[dev]")
    session.run(
        "pytest",
        "freemocap/tests/test_schema_contract.py",
        "freemocap/tests/test_settings_manager.py",
        "freemocap/tests/test_http_config_endpoints.py",
        "freemocap/tests/test_websocket_settings_protocol.py",
        "-v",
    )


@nox.session(python=False)
def test_ui(session: Session) -> None:
    """Run the frontend vitest suite (no Python needed)."""
    with session.cd("freemocap-ui"):
        session.run("npx", "vitest", "run", external=True)


@nox.session(python="3.12")
def test_all(session: Session) -> None:
    """Run backend tests, then frontend tests — the full picture."""
    session.install("-e", ".[dev]")
    session.run("pytest", "freemocap/tests", "-v")
    with session.cd("freemocap-ui"):
        session.run("npx", "vitest", "run", external=True)


@nox.session(python="3.12")
def coverage(session: Session) -> None:
    """Run a coverage report on the backend tests."""
    session.install("-e", ".[dev]", "pytest-cov")
    session.run("pytest", "--cov=freemocap", "freemocap/tests", "-v")


@nox.session(python="3.12")
def lint(session: Session) -> None:
    """Lint with ruff."""
    session.install("ruff")
    session.run("ruff", "check", "freemocap/")
