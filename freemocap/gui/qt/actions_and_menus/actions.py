from PySide6.QtCore import QUrl
from PySide6.QtGui import QAction, QDesktopServices

from freemocap.system.paths_and_filenames.file_and_folder_names import (
    DOCUMENTATION_WELCOME_URL,
    FIGSHARE_SAMPLE_ZIP_FILE_URL,
    FIGSHARE_TEST_ZIP_FILE_URL,
)

CREATE_NEW_RECORDING_ACTION_NAME = "New Recording"
LOAD_MOST_RECENT_RECORDING_ACTION_NAME = "Load Most Recent Recording"
LOAD_RECORDING_ACTION_NAME = "Load Recording"
IMPORT_VIDEOS_ACTION_NAME = "Import Videos"
DOWNLOAD_SAMPLE_DATA_ACTION_NAME = "Download Sample Data (3 cameras, ~1000 frames)"
DOWNLOAD_TEST_DATA_ACTION_NAME = "Download Test Data (3 cameras, ~200 frames)"
SET_DATA_FOLDER_ACTION_NAME = "Set Freemocap Data Folder Location"
RESET_TO_DEFAULTS_ACTION_NAME = "Reset to Default GUI Settings"
KILL_THREADS_AND_PROCESSES_ACTION_NAME = "Kill Threads and Processes"
REBOOT_GUI_ACTION_NAME = "Reboot GUI"
EXIT_ACTION_NAME = "Exit"

OPEN_DOCS_ACTION_NAME = "Open Documentation"
FREEMOCAP_FOUNDATION_ACTION_NAME = "Freemocap Foundation"

DONATE_ACTION_NAME = "Donate to Freemocap"


class Actions:
    def __init__(self, freemocap_main_window):
        # File
        self.create_new_recording_action = QAction(CREATE_NEW_RECORDING_ACTION_NAME, parent=freemocap_main_window)
        self.create_new_recording_action.setShortcut("Ctrl+N")
        self.create_new_recording_action.triggered.connect(freemocap_main_window.handle_start_new_session_action)

        self.load_most_recent_recording_action = QAction(
            LOAD_MOST_RECENT_RECORDING_ACTION_NAME, parent=freemocap_main_window
        )
        self.load_most_recent_recording_action.setShortcut("Ctrl+D")
        self.load_most_recent_recording_action.triggered.connect(
            freemocap_main_window.handle_load_most_recent_recording
        )

        self.load_existing_recording_action = QAction(LOAD_RECORDING_ACTION_NAME, parent=freemocap_main_window)
        self.load_existing_recording_action.setShortcut("Ctrl+O")
        self.load_existing_recording_action.triggered.connect(freemocap_main_window.open_load_existing_recording_dialog)

        self.import_videos_action = QAction(IMPORT_VIDEOS_ACTION_NAME, parent=freemocap_main_window)
        self.import_videos_action.setShortcut("Ctrl+I")
        self.import_videos_action.triggered.connect(freemocap_main_window.open_import_videos_dialog)

        self.download_sample_data_action = QAction(DOWNLOAD_SAMPLE_DATA_ACTION_NAME, parent=freemocap_main_window)
        self.download_sample_data_action.triggered.connect(
            lambda: freemocap_main_window.download_data(download_url=FIGSHARE_SAMPLE_ZIP_FILE_URL)
        )

        self.download_test_data_action = QAction(DOWNLOAD_TEST_DATA_ACTION_NAME, parent=freemocap_main_window)
        self.download_test_data_action.triggered.connect(
            lambda: freemocap_main_window.download_data(download_url=FIGSHARE_TEST_ZIP_FILE_URL)
        )

        self.set_data_folder_action = QAction(SET_DATA_FOLDER_ACTION_NAME, parent=freemocap_main_window)
        self.set_data_folder_action.setShortcut("Ctrl+S")
        self.set_data_folder_action.triggered.connect(freemocap_main_window.open_settings_dialog)

        self.reset_to_defaults_action = QAction(RESET_TO_DEFAULTS_ACTION_NAME, parent=freemocap_main_window)
        self.reset_to_defaults_action.triggered.connect(freemocap_main_window.reset_to_default_gui_settings)

        self.reboot_gui_action = QAction(REBOOT_GUI_ACTION_NAME, parent=freemocap_main_window)
        self.reboot_gui_action.setShortcut("Ctrl+R")
        self.reboot_gui_action.triggered.connect(freemocap_main_window.reboot_gui)

        self.kill_running_threads_and_processes_action = QAction(
            KILL_THREADS_AND_PROCESSES_ACTION_NAME, parent=freemocap_main_window
        )
        self.kill_running_threads_and_processes_action.setShortcut("Ctrl+K")
        self.kill_running_threads_and_processes_action.triggered.connect(
            freemocap_main_window.kill_running_threads_and_processes
        )

        self.exit_action = QAction("E&xit", parent=freemocap_main_window)
        self.exit_action.setShortcut("Ctrl+Q")
        self.exit_action.triggered.connect(freemocap_main_window.close)

        # Help
        self.open_docs_action = QAction(OPEN_DOCS_ACTION_NAME, parent=freemocap_main_window)
        self.open_docs_action.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl(DOCUMENTATION_WELCOME_URL))
        )

        self.freemocap_foundation_action = QAction(FREEMOCAP_FOUNDATION_ACTION_NAME, parent=freemocap_main_window)
        self.freemocap_foundation_action.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://freemocap.org/about-us.html"))
        )

        # # Navigation
        # show_camera_control_panel_action = QAction("&1 - Show Camera Control Panel", parent=main_window)
        # show_camera_control_panel_action.setShortcut("Ctrl+1")
        #
        # show_calibrate_capture_volume_panel_action = QAction(
        #     "&2 - Show Calibrate Capture Volume Panel", parent=main_window
        # )
        # show_calibrate_capture_volume_panel_action.setShortcut("Ctrl+2")
        #
        # show_motion_capture_videos_panel_action = QAction("&3 - Show Motion Capture Videos Panel", parent=main_window)
        # show_motion_capture_videos_panel_action.setShortcut("Ctrl+3")
        #
        # Support
        self.donate_action = QAction(DONATE_ACTION_NAME, parent=freemocap_main_window)
        self.donate_action.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://freemocap.org/about-us.html#donate"))
        )
        # self.send_usage_statistics_action = QAction("Send &User Statistics", parent=freemocap_main_window)
        # self.user_survey_action = QAction("&User Survey", parent=freemocap_main_window)
