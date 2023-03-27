from PyQt6.QtGui import QAction


CREATE_NEW_RECORDING_ACTION_NAME = "New Recording"
LOAD_MOST_RECENT_RECORDING_ACTION_NAME = "Load Most Recent Recording"
LOAD_RECORDING_ACTION_NAME = "Load Recording"
IMPORT_VIDEOS_ACTION_NAME = "Import Videos"
KILL_THREADS_AND_PROCESSES_ACTION_NAME = "Kill Threads and Processes"
REBOOT_GUI_ACTION_NAME = "Reboot GUI"
EXIT_ACTION_NAME = "Exit"


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

        # # Help
        # open_docs_action = QAction("Open  &Documentation", parent=main_window)
        # about_us_action = QAction("&About Us", parent=main_window)
        #
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
        # # Support
        # donate_action = QAction("&Donate", parent=main_window)
        # send_usage_statistics_action = QAction("Send &User Statistics", parent=main_window)
        # user_survey_action = QAction("&User Survey", parent=main_window)
