# __main__.py
import sys
from multiprocessing import freeze_support
from pathlib import Path


try:
    from freemocap.gui.qt.freemocap_main import qt_gui_main
except Exception:
    base_package_path = Path(__file__).parent.parent
    print(f"adding base_package_path: {base_package_path} : to sys.path")
    sys.path.insert(0, str(base_package_path))  # add parent directory to sys.path
    from freemocap.gui.qt.freemocap_main import qt_gui_main


def main():
    # set up so you can change the taskbar icon - https://stackoverflow.com/a/74531530/14662833
    import ctypes
    import freemocap

    if sys.platform == "win32":
        myappid = f"{freemocap.__package_name__}_{freemocap.__version__}"  # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    qt_gui_main()


if __name__ == "__main__":
    freeze_support()
    print(f"Running `freemocap.__main__` from - {__file__}")

    main()
