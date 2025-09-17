import logging
import threading

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTabWidget,
    QWidget,
    QScrollArea,  # Added import
)

from freemocap.gui.qt.utilities.save_and_load_gui_state import GuiState, load_gui_state
from freemocap.gui.qt.widgets.release_notes_dialogs.release_notes_content import get_all_release_notes, \
    ReleaseNoteContent
from freemocap.gui.qt.widgets.release_notes_dialogs.release_notes_styles import ReleaseNotesStyles

logger = logging.getLogger(__name__)

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
            min_width: int = 1000,
            min_height: int =800,
            dark_mode: bool = True,
    ) -> None:
        super().__init__(parent=parent)
        self.kill_thread_event = kill_thread_event
        self.gui_state = gui_state
        self.dark_mode = dark_mode

        self.setMinimumSize(min_width, min_height)
        self.setWindowTitle("FreeMoCap Release Notes")
        self.setStyleSheet(
            ReleaseNotesStyles.get_dialog_style(
                dark_mode=self.dark_mode))

        # Main layout - horizontal to support side tabs
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        self.setLayout(main_layout)

        # Create tab widget with tabs on the left side
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.South)  # Set tabs to the left side
        self.tab_widget.setStyleSheet(
            ReleaseNotesStyles.get_tab_widget_style(
                dark_mode=self.dark_mode))

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
        release_notes: list[ReleaseNoteContent] = get_all_release_notes()

        # Add each release note as a tab
        for release_note in release_notes:
            tab = QWidget()
            layout = QVBoxLayout(tab)
            layout.setContentsMargins(20, 20, 20, 20)

            # Create content widget - now passing image_path
            content_widget = self._create_release_notes_content(release_note)
            layout.addWidget(content_widget)

            # Add tab
            self.tab_widget.addTab(tab, release_note.tab_title)

    def _create_release_notes_content(
            self,
            release_note: ReleaseNoteContent,
    ) -> QWidget:
        """Create a widget with release notes content."""
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(20)

        # Create scroll area for text content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("background-color: transparent;"
                                  "border: none;")

        # Create a container widget for the scrollable content
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)


        scroll_layout.setSpacing(15)

        title_widget = QLabel()
        title_widget.setWordWrap(True)
        title_widget.setOpenExternalLinks(True)

        # Title HTML content with inline styles
        title_html_content = f"""
        <html>
        <head>
            <style>
                .title {{
                    font-size: 24px;
                    font-weight: bold;
                    color: {'#ffffff' if self.dark_mode else '#1a1a1a'};
                    margin-bottom: 10px;
                    line-height: 1.3;
                }}
            </style>
        </head>
        <body>
            <div class="title">{release_note.content_title}</div>
        </body>
        </html>
        """
        title_widget.setText(title_html_content)
        scroll_layout.addWidget(title_widget)

        if release_note.content_subtitle:
            subtitle_widget = QLabel()
            subtitle_widget.setWordWrap(True)
            subtitle_widget.setOpenExternalLinks(True)

            # Apply styling directly to the widget
            subtitle_widget.setStyleSheet(f"""
                        QLabel {{
                            font-size: 16px;
                            font-weight: bold;
                            color: {'#4fc3f7' if self.dark_mode else '#2196F3'};
                            padding: 15px 0px 10px 0px;
                        }}
                    """)

            # Simple text content - no HTML styling needed
            subtitle_widget.setText(release_note.content_subtitle)
            scroll_layout.addWidget(subtitle_widget)
        # Add image if provided
        if release_note.image_path:
            from pathlib import Path
            if Path(release_note.image_path).exists():
                image_label = QLabel()
                image_label.setAlignment(Qt.AlignCenter)
                image_pixmap = QPixmap(release_note.image_path)

                if not image_pixmap.isNull():
                    # Scale image to fit within scroll area while maintaining aspect ratio
                    max_width =540
                    if image_pixmap.width() > max_width:
                        scaled_pixmap = image_pixmap.scaledToWidth(
                            max_width,
                            Qt.SmoothTransformation
                        )
                    else:
                        scaled_pixmap = image_pixmap

                    image_label.setPixmap(scaled_pixmap)

                    # Add some spacing and the image
                    scroll_layout.addSpacing(10)
                    scroll_layout.addWidget(image_label)
                    scroll_layout.addSpacing(10)
                else:
                    logger.warning(f"Failed to load image: {release_note.image_path}")
            else:
                logger.warning(f"Image file does not exist: {release_note.image_path}")

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
        {release_note.content_html}
        </body>
        </html>
        """
        text_widget.setText(html_content)
        scroll_layout.addWidget(text_widget)


        # Add stretch to push content to top
        scroll_layout.addStretch()

        # Set the scroll content widget
        scroll_area.setWidget(scroll_content)

        # Add scroll area to layout
        content_layout.addWidget(scroll_area, 1)

        # Logo (on the right side)
        if release_note.logo_path:
            logo_label = QLabel()
            logo_label.setFixedSize(QSize(200, 200))
            logo_label.setAlignment(Qt.AlignCenter)

            pixmap = QPixmap(release_note.logo_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                logo_label.setPixmap(scaled_pixmap)
            else:
                logger.warning(f"Failed to load logo: {release_note.logo_path}")

            content_layout.addWidget(logo_label, 0, Qt.AlignTop)

        return content_widget


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Show the new tabbed dialog with dark mode enabled
    dialog = TabbedReleaseNotesDialog(
        gui_state=load_gui_state(),
        kill_thread_event=threading.Event(),
        dark_mode=True,  # Set to True for dark mode, False for light mode
    )
    dialog.show()

    sys.exit(app.exec())