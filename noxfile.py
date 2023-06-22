import nox

@nox.session(python=["3.8","3.9", "3.10", "3.11"])
def test(session):
    """Run the full test suite on python versions 3.8, 3.9, 3.10, 3.11."""
    session.install("-e", ".")
    session.run("pytest", "freemocap/tests")