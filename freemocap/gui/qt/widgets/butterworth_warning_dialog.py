import threading

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QCheckBox,
    QPushButton,
    QSpacerItem,
    QSizePolicy,
)

from freemocap.gui.qt.utilities.save_and_load_gui_state import GuiState, save_gui_state
from freemocap.system.paths_and_filenames.file_and_folder_names import PATH_TO_FREEMOCAP_LOGO_SVG
from freemocap.system.paths_and_filenames.path_getters import get_gui_state_json_path

SKELLY_SWEAT_SVG = PATH_TO_FREEMOCAP_LOGO_SVG.replace("freemocap-logo-black-border.svg", "skelly-sweat.png")


class Version_1_5_4_DataWarningDialog(QDialog):
    def __init__(self, gui_state: GuiState, kill_thread_event: threading.Event, parent=None) -> None:
        super().__init__(parent=parent)
        self.gui_state = gui_state
        self.kill_thread_event = kill_thread_event

        self.setMinimumSize(700, 400)
        self.setWindowTitle("Data Quality Advisory")
        self.setStyleSheet(
            """
            QDialog {
                background-color: #f8f9fa;
            }
            QLabel {
                color: #212529;
            }
            QCheckBox {
                color: #495057;
            }
        """
        )

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)
        self.setLayout(main_layout)

        # Header Section
        header_layout = QHBoxLayout()
        header_layout.setSpacing(30)

        # Text Content
        text_layout = QVBoxLayout()
        text_layout.setSpacing(15)
        warning_text = """
            <html>
            <style>
            a {{ color: #2980b9; text-decoration: none; font-weight: 500; }}
            .emphasis {{ color: #c0392b; font-weight: bold; }}
            </style>
            <body>
            <p style="font-size: 18px; font-weight: bold; color: #2c3e50; margin-bottom: 15px;">
                Whoops!!
            </p>
            <p style="font-size: 16px; font-weight: semibold; color: #2c3e50;   margin-bottom: 15px;">
                Possible data Quality Regression in versions 1.4.7-1.5.3
            </p>

            <p>We identified and fixed a bug in <b>v1.4.7-v1.5.3 (10 Oct 2024 - 10 Mar 2025)</b> that caused the pipeline to Butterworth filtering during processing (<a href="https://github.com/freemocap/freemocap/pull/675">Bugfix PR</a>).
            Recordings from these versions may have increased noise/jitter/shakiness in the final keypoint trajectories.
            <br/><br/>
            Based on your application, the difference may or may not be noticeable. It is most likely to affect users who's applications focus on fine grained trajectories of the hands and limbs (especially for scientific analysis)
            <br/><br/>
            <b>We recommend reprocessing any critical data collected during this period with the latest version of FreeMoCap to ensure the highest quality results.</b>
            <br/><br/>
             You may also filter the data in Blender (see <a href="https://www.youtube.com/watch?v=33OhM5xFUlg">this tutorial Flux Renders</a>)
            <br/>
            --
            <br>
            In preparation for the release of FreeMoCap v2.0 (optimistically Summer 2025), we are implementing a <a href="https://github.com/freemocap/freemocap/pull/676"> set of comprehensive quality assurance diagnostics </a>to ensure that the quality of our output is strictly monotonic across future versions.

            <p style="font-size: 13px; margin-top: 20px; color: #7f8c8d;">
            Thanks to  (<a href="https://discord.com/channels/760487252379041812/760489602917466133/1346487740568440983">@larap for reporting</a>), and to the rest of the freemocap community for their help in developing this project.
            </p>
            </body>
            </html>
        """

        content = QLabel(warning_text)
        content.setStyleSheet(
            """
            font-size: 14px;
            line-height: 1.4;
            color: #2c3e50;
        """
        )
        content.setWordWrap(True)
        content.setOpenExternalLinks(True)

        text_layout.addWidget(content)
        header_layout.addLayout(text_layout, 1)

        # Logo
        logo_label = QLabel()
        logo_label.setFixedSize(QSize(150, 150))
        logo_label.setAlignment(Qt.AlignCenter)  # Center the image in the label

        pixmap = QPixmap(SKELLY_SWEAT_SVG)
        if not pixmap.isNull():
            # Scale the pixmap to fit within 150x150 while maintaining aspect ratio
            scaled_pixmap = pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            logo_label.setPixmap(scaled_pixmap)
        else:
            print(f"Failed to load image: {SKELLY_SWEAT_SVG}")

        header_layout.addWidget(logo_label, 0, Qt.AlignTop)

        main_layout.addLayout(header_layout)

        # Bottom Controls
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(20)

        self._dont_show_again_checkbox = QCheckBox("Don't show this message again")
        self._dont_show_again_checkbox.setStyleSheet("font-size: 13px;")
        self._dont_show_again_checkbox.stateChanged.connect(self._dont_show_again_checkbox_changed)

        done_btn = QPushButton("Ok")
        done_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 5px;
                border: 1px solid #3498db;
                padding: 10px 25px;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """
        )
        done_btn.clicked.connect(self.accept)

        controls_layout.addWidget(self._dont_show_again_checkbox)
        controls_layout.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        controls_layout.addWidget(done_btn)

        main_layout.addLayout(controls_layout)

    def _dont_show_again_checkbox_changed(self) -> None:
        self.gui_state.show_data_quality_warning = not self._dont_show_again_checkbox.isChecked()
        save_gui_state(gui_state=self.gui_state, file_pathstring=get_gui_state_json_path())


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    dialog = Version_1_5_4_DataWarningDialog(gui_state=GuiState(), kill_thread_event=threading.Event())
    dialog.show()
    sys.exit(app.exec())
