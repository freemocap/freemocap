import threading
from typing import Optional

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


class ReleaseNotesDialog(QDialog):
    """
    Base class for displaying release notes, warnings, or other informational dialogs.
    
    Subclasses should override the methods to customize the content and behavior.
    """
    
    def __init__(
        self, 
        gui_state: GuiState, 
        kill_thread_event: threading.Event, 
        parent=None,
        min_width: int = 700,
        min_height: int = 400,
    ) -> None:
        super().__init__(parent=parent)
        self.gui_state = gui_state
        self.kill_thread_event = kill_thread_event

        self.setMinimumSize(min_width, min_height)
        self.setWindowTitle(self.get_window_title())
        self.setStyleSheet(self.get_dialog_style())

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

        content = QLabel(self.get_content_html())
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
        logo_path = self.get_logo_path()
        if logo_path:
            logo_label = QLabel()
            logo_label.setFixedSize(QSize(150, 150))
            logo_label.setAlignment(Qt.AlignCenter)

            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                logo_label.setPixmap(scaled_pixmap)
            else:
                print(f"Failed to load image: {logo_path}")

            header_layout.addWidget(logo_label, 0, Qt.AlignTop)

        main_layout.addLayout(header_layout)

        # Bottom Controls
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(20)

        # Only add checkbox if show_again_flag_name is provided
        show_again_flag_name = self.get_show_again_flag_name()
        if show_again_flag_name:
            self._dont_show_again_checkbox = QCheckBox("Don't show this message again")
            self._dont_show_again_checkbox.setStyleSheet("font-size: 13px;")
            self._dont_show_again_checkbox.stateChanged.connect(self._dont_show_again_checkbox_changed)
            controls_layout.addWidget(self._dont_show_again_checkbox)
        
        controls_layout.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        done_btn = QPushButton(self.get_button_text())
        done_btn.setStyleSheet(self.get_button_style())
        done_btn.clicked.connect(self.accept)
        controls_layout.addWidget(done_btn)

        main_layout.addLayout(controls_layout)

    def _dont_show_again_checkbox_changed(self) -> None:
        """Handle the 'don't show again' checkbox state change."""
        flag_name = self.get_show_again_flag_name()
        if flag_name and hasattr(self.gui_state, flag_name):
            setattr(self.gui_state, flag_name, not self._dont_show_again_checkbox.isChecked())
            save_gui_state(gui_state=self.gui_state, file_pathstring=get_gui_state_json_path())

    def get_window_title(self) -> str:
        """Return the window title for the dialog."""
        raise NotImplementedError("Subclasses must implement get_window_title()")

    def get_content_html(self) -> str:
        """Return the HTML content to display in the dialog."""
        raise NotImplementedError("Subclasses must implement get_content_html()")

    def get_logo_path(self) -> Optional[str]:
        """Return the path to the logo image, or None if no logo should be displayed."""
        raise NotImplementedError("Subclasses must implement get_logo_path()")

    def get_show_again_flag_name(self) -> Optional[str]:
        """
        Return the name of the attribute in gui_state to control showing this dialog again.
        
        Return None if the dialog should always be shown.
        """
        return None

    def get_button_text(self) -> str:
        """Return the text for the confirmation button."""
        return "Ok"

    def get_dialog_style(self) -> str:
        """Return the CSS style for the dialog."""
        return """
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

    def get_button_style(self) -> str:
        """Return the CSS style for the confirmation button."""
        return """
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


class NewFeatureReleaseNotesDialog(ReleaseNotesDialog):
    def __init__(self, gui_state: GuiState, kill_thread_event: threading.Event, parent=None) -> None:
        super().__init__(
            gui_state=gui_state, 
            kill_thread_event=kill_thread_event, 
            parent=parent,
            min_width=800,  # Custom width
            min_height=500,  # Custom height
        )

    def get_window_title(self) -> str:
        return "New Features in FreeMoCap v2.0"

    def get_content_html(self) -> str:
        return """
            <html>
            <style>
            a { color: #2980b9; text-decoration: none; font-weight: 500; }
            .feature { color: #27ae60; font-weight: bold; }
            </style>
            <body>
            <p style="font-size: 20px; font-weight: bold; color: #2c3e50; margin-bottom: 15px;">
                FreeMoCap v2.0 is Here!
            </p>
            
            <p>We're excited to announce the release of FreeMoCap v2.0 with several major improvements:</p>
            
            <ul>
                <li><span class="feature">Enhanced Tracking Accuracy:</span> Improved algorithms for more precise motion capture</li>
                <li><span class="feature">Real-time Feedback:</span> Get immediate visual feedback during recording sessions</li>
                <li><span class="feature">Extended Export Options:</span> New formats including FBX and BVH for better compatibility</li>
                <li><span class="feature">Streamlined UI:</span> Redesigned interface for improved workflow</li>
            </ul>
            
            <p>Check out our <a href="https://github.com/freemocap/freemocap/releases">release notes</a> for full details and our 
            <a href="https://freemocap.org/tutorial">tutorials</a> to get started with the new features.</p>
            
            <p style="font-size: 13px; margin-top: 20px; color: #7f8c8d;">
            Thank you to all our contributors and users for your continued support!
            </p>
            </body>
            </html>
        """

    def get_logo_path(self) -> Optional[str]:
        return PATH_TO_FREEMOCAP_LOGO_SVG

    def get_show_again_flag_name(self) -> Optional[str]:
        return "show_v2_release_notes"
        
    def get_button_text(self) -> str:
        return "Let's Go!"  # Custom button text


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    dialog = NewFeatureReleaseNotesDialog(gui_state=GuiState(), kill_thread_event=threading.Event())
    dialog.show()
    sys.exit(app.exec())