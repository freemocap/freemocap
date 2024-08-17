# __main__.py
import multiprocessing
import sys
from multiprocessing import freeze_support, Process
from pathlib import Path

from freemocap.api import run_server
from freemocap.api.run_server import run_uvicorn_server


try:
    from freemocap.gui.qt.run_gui import qt_gui_main, logger
except Exception:
    base_package_path = Path(__file__).parent.parent
    print(f"adding base_package_path: {base_package_path} : to sys.path")
    sys.path.insert(0, str(base_package_path))  # add parent directory to sys.path
    from freemocap.gui.qt.run_gui import qt_gui_main


def main():
    # set up so you can change the taskbar icon - https://stackoverflow.com/a/74531530/14662833
    import ctypes
    import freemocap
    multiprocessing.freeze_support()

    frontend_process = multiprocessing.Process(target=qt_gui_main)
    logger.info(f"Starting frontend process")
    frontend_process.start()

    backend_process = Process(target=run_uvicorn_server)
    logger.info(f"Starting backend process")
    backend_process.start()

    frontend_process.join()
    backend_process.join()
    logger.info(f"Exiting `main`...")



if __name__ == "__main__":
    freeze_support()
    print(f"Running `freemocap.__main__` from - {__file__}")

    main()
    print(f"Thank you for using freemocap \U0001F480 \U00002764 \U00002728")
