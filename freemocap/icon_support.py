# Why do i exist again?
import ctypes
import sys

import freemocap


def handle_icons():
    """
    Something about windows and icons. You got this Jon
    """
    if sys.platform == "win32":
        myappid = f"{freemocap.__package_name__}_{freemocap.__version__}"  # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
