import nox
from nox.sessions import Session


@nox.session(python=["3.10", "3.11", "3.12"])
def test(session: Session):
    """Run the full test suite on python versions 3.10, 3.11, and 3.12."""
    session.install("-e", ".")
    session.run("pytest", "freemocap/tests")


@nox.session(python=["3.10"])
def test_10(session: Session):
    """Run the full test suite on python versions 3.10."""
    session.install("-e", ".")
    session.run("pytest", "freemocap/tests")


@nox.session(python=["3.11", "3.12"])
def test_11_12(session: Session):
    """Run the full test suite on python versions 3.11 and 3.12."""
    session.install("-e", ".")
    session.run("pytest", "freemocap/tests")


@nox.session(python="3.12")
def coverage(session: Session):
    """Run a coverage test on python 3.12."""
    session.install("-e", ".", "pytest-cov")
    session.run("pytest", "--cov=freemocap", "freemocap/tests")


@nox.session(python="3.12")
def lint(session: Session):
    """Lint using Flake8"""
    session.install(
        "flake8",
        "flake8-bandit",
        "flake8-bugbear",
    )
    session.run("flake8")
