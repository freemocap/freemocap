import logging
import os
import signal
import sys
from importlib.metadata import distributions
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QTimer
from PySide6.QtWidgets import QApplication

from freemocap.gui.qt.main_window.freemocap_main_window import MainWindow, EXIT_CODE_REBOOT

logging.getLogger("matplotlib").setLevel(logging.WARNING)

from freemocap.gui.qt.utilities.get_qt_app import get_qt_app
from freemocap.system.paths_and_filenames.path_getters import get_freemocap_data_folder_path
from freemocap.system.user_data.pipedream_pings import PipedreamPings

repo = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(repo))

logger = logging.getLogger(__name__)


def sigint_handler(*args):
    """Handler for the SIGINT signal."""
    QApplication.quit()


def _normalize_qt_plugin_environment():
    if not sys.platform.startswith("linux"):
        return

    cv2_qt_plugins_fragment = f"{Path('cv2') / 'qt' / 'plugins'}".replace("\\", "/")

    qt_plugin_path = os.environ.get("QT_PLUGIN_PATH")
    if qt_plugin_path:
        plugin_paths = [
            plugin_path
            for plugin_path in qt_plugin_path.split(os.pathsep)
            if cv2_qt_plugins_fragment not in plugin_path.replace("\\", "/")
        ]
        if plugin_paths:
            os.environ["QT_PLUGIN_PATH"] = os.pathsep.join(plugin_paths)
        else:
            os.environ.pop("QT_PLUGIN_PATH", None)

    pyside_platform_plugins_path = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)) / "platforms"
    if pyside_platform_plugins_path.exists():
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(pyside_platform_plugins_path)


def qt_gui_main():
    logger.info("Starting main...")
    signal.signal(signal.SIGINT, sigint_handler)
    _normalize_qt_plugin_environment()
    app = get_qt_app()
    timer = QTimer()
    timer.start(500)

    pipedream_pings = PipedreamPings()

    while True:
        freemocap_main_window = MainWindow(
            freemocap_data_folder_path=get_freemocap_data_folder_path(), pipedream_pings=pipedream_pings
        )
        logger.info("Showing main window - Ready to start!")

        freemocap_main_window.show()

        handle_pop_ups(freemocap_main_window)

        timer.timeout.connect(freemocap_main_window.update)
        error_code = app.exec()
        logger.info(f"`main` exited with error code: {error_code}")
        freemocap_main_window.close()

        if not error_code == EXIT_CODE_REBOOT:
            print("Thank you for using freemocap \U0001f480 \U00002764 \U00002728")
            break

        logger.info("`main` exited with the 'reboot' code, so let's reboot!")

    sys.exit()


def handle_pop_ups(freemocap_main_window: MainWindow):
    if freemocap_main_window._gui_state.show_welcome_screen:
        freemocap_main_window.open_welcome_screen_dialog()
    if not freemocap_main_window._gui_state.shown_latest_release_notes:
        freemocap_main_window.open_release_notes_popup()

    installed_packages = {dist.metadata["Name"] for dist in distributions()}
    if "opencv-python" in installed_packages and "opencv-contrib-python" in installed_packages:
        freemocap_main_window.open_opencv_conflict_dialog()


if __name__ == "__main__":
    qt_gui_main()
