import threading

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QWidget,
    QRadioButton,
    QButtonGroup,
    QGroupBox,
)

from freemocap.gui.qt.utilities.save_and_load_gui_state import GuiState, load_gui_state
from freemocap.gui.qt.widgets.release_notes_dialogs.release_notes_content import get_all_release_notes
from freemocap.gui.qt.widgets.release_notes_dialogs.release_notes_styles import ReleaseNotesStyles
from freemocap.gui.qt.widgets.release_notes_dialogs.tabbed_release_notes_types import ReleaseNotesDisplayOption


class TabbedReleaseNotesDialog(QDialog):
    """
    A tabbed dialog that displays release notes from current and previous versions,
    with options to control when the dialog is shown.
    """

    def __init__(
        self,
        kill_thread_event: threading.Event,
        gui_state: GuiState,
        parent=None,
        min_width: int = 900,
        min_height: int = 550,
        dark_mode: bool = True,
    ) -> None:
        super().__init__(parent=parent)
        self.kill_thread_event = kill_thread_event
        self.gui_state = gui_state
        self.dark_mode = dark_mode

        self.setMinimumSize(min_width, min_height)
        self.setWindowTitle("FreeMoCap Release Notes")
        self.setStyleSheet(ReleaseNotesStyles.get_dialog_style(dark_mode=self.dark_mode))

        # Main layout - horizontal to support side tabs
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        self.setLayout(main_layout)

        # Create tab widget with tabs on the left side
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.South)  # Set tabs to the left side
        self.tab_widget.setStyleSheet(ReleaseNotesStyles.get_tab_widget_style(dark_mode=self.dark_mode))

        self.tab_widget.tabBar().setElideMode(Qt.ElideNone)

        # Add tabs for different release notes
        self._add_release_notes_tabs()

        main_layout.addWidget(self.tab_widget, 1)

        # Right side panel for options
        # options_panel = self._create_options_panel()
        # main_layout.addWidget(options_panel, 0)  # Fixed width for options panel

    def _add_release_notes_tabs(self) -> None:
        """Add tabs for different release notes."""
        # Get all release notes content
        release_notes = get_all_release_notes()

        # Add each release note as a tab
        for release_note in release_notes:
            tab = QWidget()
            layout = QVBoxLayout(tab)
            layout.setContentsMargins(20, 20, 20, 20)

            # Create content widget
            content_widget = self._create_release_notes_content(
                title=release_note.content_title, content=release_note.content_html, logo_path=release_note.logo_path
            )
            layout.addWidget(content_widget)

            # Add tab
            self.tab_widget.addTab(tab, release_note.tab_title)

    def _create_release_notes_content(self, title: str, content: str, logo_path: str = None) -> QWidget:
        """Create a widget with release notes content."""
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(20)

        # Text content
        text_widget = QLabel()
        text_widget.setWordWrap(True)
        text_widget.setOpenExternalLinks(True)
        text_widget.setStyleSheet(
            """
            font-size: 14px;
            line-height: 1.4;
            color: #e0e0e0;
        """
            if self.dark_mode
            else """
            font-size: 14px;
            line-height: 1.4;
            color: #2c3e50;
        """
        )

        # Set HTML content
        html_content = f"""
        <html>
        {ReleaseNotesStyles.get_html_content_style(dark_mode=self.dark_mode)}
        <body>
        <p style="font-size: 20px; font-weight: bold; color: {'#e0e0e0' if self.dark_mode else '#2c3e50'}; margin-bottom: 15px;">
            {title}
        </p>
        {content}
        </body>
        </html>
        """
        text_widget.setText(html_content)

        content_layout.addWidget(text_widget, 1)

        # Logo
        if logo_path:
            logo_label = QLabel()
            logo_label.setFixedSize(QSize(200, 200))
            logo_label.setAlignment(Qt.AlignCenter)

            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                logo_label.setPixmap(scaled_pixmap)
            else:
                print(f"Failed to load image: {logo_path}")

            content_layout.addWidget(logo_label, 0, Qt.AlignTop)

        return content_widget




if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Show the new tabbed dialog with dark mode enabled
    dialog = TabbedReleaseNotesDialog(
        gui_state=load_gui_state(),
        kill_thread_event=threading.Event(), dark_mode=True  # Set to True for dark mode, False for light mode
    )
    dialog.show()

    sys.exit(app.exec())
