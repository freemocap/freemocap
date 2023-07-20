import os
import subprocess
import sys


def open_file(filename):
    if sys.platform == "win32":
        os.startfile(filename)  # noqa
    else:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.call([opener, filename])
