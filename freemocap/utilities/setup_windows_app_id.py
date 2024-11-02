import sys


def setup_app_id_for_windows():
    if sys.platform == "win32":
        # set up so you can change the taskbar icon - https://stackoverflow.com/a/74531530/14662833
        import ctypes
        import skellycam

        myappid = f"{skellycam.__package_name__}_{skellycam.__version__}"  # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
