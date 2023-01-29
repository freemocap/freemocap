from typing import Dict

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMainWindow, QMenu, QMenuBar


START_NEW_SESSION_ACTION_NAME = "Start New Session"
LOAD_EXISTING_RECORDING_ACTION_NAME = "Load Existing Recording"
LOAD_MOST_RECENT_RECORDING_ACTION_NAME = "Load Most Recent Recording"
IMPORT_VIDEOS_ACTION_NAME = "Import Videos"
REBOOT_GUI_ACTION_NAME = "Reboot GUI"
EXIT_ACTION_NAME = "Exit"


class MenuBar(QMenuBar):
    def __init__(self, parent: QMainWindow = None):
        super().__init__(parent=parent)

        self._actions_dictionary = self._create_actions_dictionary()
        self._add_actions()

    @property
    def actions_dictionary(self) -> Dict[str, QAction]:
        return self._actions_dictionary

    def _create_actions_dictionary(self) -> Dict[str, QAction]:
        actions_dictionary = {}
        actions_dictionary[START_NEW_SESSION_ACTION_NAME] = QAction(START_NEW_SESSION_ACTION_NAME, parent=self.parent())
        actions_dictionary[START_NEW_SESSION_ACTION_NAME].setShortcut("Ctrl+N")

        actions_dictionary[LOAD_MOST_RECENT_RECORDING_ACTION_NAME] = QAction(
            LOAD_MOST_RECENT_RECORDING_ACTION_NAME, parent=self.parent()
        )
        actions_dictionary[LOAD_MOST_RECENT_RECORDING_ACTION_NAME].setShortcut("Ctrl+D")

        actions_dictionary[LOAD_EXISTING_RECORDING_ACTION_NAME] = QAction(
            LOAD_EXISTING_RECORDING_ACTION_NAME, parent=self.parent()
        )
        actions_dictionary[LOAD_EXISTING_RECORDING_ACTION_NAME].setShortcut("Ctrl+O")

        actions_dictionary[IMPORT_VIDEOS_ACTION_NAME] = QAction(IMPORT_VIDEOS_ACTION_NAME, parent=self.parent())
        actions_dictionary[IMPORT_VIDEOS_ACTION_NAME].setShortcut("Ctrl+I")

        actions_dictionary[REBOOT_GUI_ACTION_NAME] = QAction("&Reboot GUI", parent=self.parent())
        actions_dictionary[REBOOT_GUI_ACTION_NAME].setShortcut("Ctrl+R")

        actions_dictionary[EXIT_ACTION_NAME] = QAction("&Exit", parent=self.parent())
        actions_dictionary[EXIT_ACTION_NAME].setShortcut("Ctrl+Q")

        #
        # # Help
        # self._open_docs_action = QAction("Open  &Documentation", parent=self)
        # self._about_us_action = QAction("&About Us", parent=self)
        #
        # # Navigation
        # self._show_camera_control_panel_action = QAction(            "&1 - Show Camera Control Panel", parent=self)
        # self._show_camera_control_panel_action.setShortcut("Ctrl+1")
        #
        # self._show_calibrate_capture_volume_panel_action = QAction(
        #     "&2 - Show Calibrate Capture Volume Panel", parent=self)
        # self._show_calibrate_capture_volume_panel_action.setShortcut("Ctrl+2")
        #
        # self._show_motion_capture_videos_panel_action = QAction(
        #     "&3 - Show Motion Capture Videos Panel", parent=self)
        # self._show_motion_capture_videos_panel_action.setShortcut("Ctrl+3")
        #
        # # Support
        # self._donate_action = QAction("&Donate", parent=self)
        # self._send_usage_statistics_action = QAction(
        #     "Send &User Statistics", parent=self)
        # self._user_survey_action = QAction("&User Survey", parent=self)

        return actions_dictionary

    def _add_actions(self):
        """
        based mostly on: https://realpython.com/python-menus-toolbars/
        """

        # file menu
        file_menu = self.addMenu("&File")

        file_menu.addAction(self._actions_dictionary[START_NEW_SESSION_ACTION_NAME])
        file_menu.addAction(self._actions_dictionary[LOAD_MOST_RECENT_RECORDING_ACTION_NAME])
        file_menu.addAction(self._actions_dictionary[LOAD_EXISTING_RECORDING_ACTION_NAME])
        file_menu.addAction(self._actions_dictionary[IMPORT_VIDEOS_ACTION_NAME])
        file_menu.addAction(self._actions_dictionary[REBOOT_GUI_ACTION_NAME])
        file_menu.addAction(self._actions_dictionary[EXIT_ACTION_NAME])
        #
        # # navigation menu
        # navigation_menu = QMenu("Na&vigation", parent=self)
        # self.addMenu(navigation_menu)
        #
        # navigation_menu.addAction(self._show_camera_control_panel_action)
        # navigation_menu.addAction(self._show_calibrate_capture_volume_panel_action)
        # navigation_menu.addAction(self._show_motion_capture_videos_panel_action)
        #
        # # help menu
        # help_menu = QMenu("&Help", parent=self)
        # self.addMenu(help_menu)
        # help_menu.setEnabled(False)
        #
        # help_menu.addAction(self._open_docs_action)
        # help_menu.addAction(self._about_us_action)
        #
        # # support menu
        # support_menu = QMenu(
        #     "\U00002665 &Support the FreeMoCap Project", parent=self
        # )
        # support_menu.setEnabled(False)
        # self.addMenu(support_menu)
        #
        # support_menu.addAction(self._donate_action)
        # support_menu.addAction(self._send_usage_statistics_action)
        # support_menu.addAction(self._user_survey_action)


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication, QLabel

    app = QApplication(sys.argv)
    _main_window = QMainWindow()
    _main_window.setCentralWidget(QLabel("Henlo fren"))
    _menu_bar = MenuBar(parent=_main_window)
    # _menu_bar = QMenuBar(parent=_main_window)
    # _fake_menu = QMenu("&Fake Menu", parent=_menu_bar)
    # _menu_bar.addMenu(_fake_menu)
    # _fake_menu.addAction("Fake Action")
    _main_window.setMenuBar(_menu_bar)
    _main_window.show()
    sys.exit(app.exec())
