from PyQt6.QtGui import QAction, QDesktopServices
from PyQt6.QtCore import QUrl


CREATE_NEW_RECORDING_ACTION_NAME = "New Recording"
LOAD_MOST_RECENT_RECORDING_ACTION_NAME = "Load Most Recent Recording"
LOAD_RECORDING_ACTION_NAME = "Load Recording"
IMPORT_VIDEOS_ACTION_NAME = "Import Videos"
KILL_THREADS_AND_PROCESSES_ACTION_NAME = "Kill Threads and Processes"
REBOOT_GUI_ACTION_NAME = "Reboot GUI"
EXIT_ACTION_NAME = "Exit"

DOCUMENTATION_ACTION_NAME = "Open Documentation"
ABOUT_US_ACTION_NAME = "About Us"

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
        self.open_docs_action = QAction(DOCUMENTATION_ACTION_NAME, parent=freemocap_main_window)
        self.open_docs_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl("https://freemocap.readthedocs.io/en/latest/")))
        
        self.about_us_action = QAction(ABOUT_US_ACTION_NAME, parent=freemocap_main_window)

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
        self.donate_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl("https://freemocap.org/about-us.html#donate")))
        # self.send_usage_statistics_action = QAction("Send &User Statistics", parent=freemocap_main_window)
        # self.user_survey_action = QAction("&User Survey", parent=freemocap_main_window)
