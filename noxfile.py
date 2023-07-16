import nox
from nox.sessions import Session


@nox.session(python=["3.8", "3.9", "3.10", "3.11"])
def test(session: Session):
    """Run the full test suite on python versions 3.8, 3.9, 3.10, 3.11."""
    session.install("-e", ".")
    session.run("pytest", "freemocap/tests")


@nox.session(python="3.11")
def coverage(session: Session):
    """Run a coverage test on python 3.11."""
    session.install("-e", ".[dev]")
    session.run("pytest", "--cov=freemocap", "freemocap/tests")
