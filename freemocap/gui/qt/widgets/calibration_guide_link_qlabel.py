from typing import Optional

from PySide6.QtCore import Qt, QObject
from PySide6.QtGui import QDesktopServices, QCursor
from PySide6.QtWidgets import QLabel

CALIBRATION_DOCS_LINK = "https://freemocap.github.io/documentation/multi-camera-calibration.html"


class CalibrationGuideLinkQLabel(QLabel):
    """A reusable widget that displays a clickable link to the calibration documentation."""

    def __init__(
            self,
            text: str | None = None,
            url: str | None = None,
            parent: Optional[QObject] = None,
    ):
        """
        Initialize the CalibrationGuideLink widget.

        Args:
            text: The link text to display. Defaults to "📚 Calibration Guide"
            url: The URL to open. Defaults to CALIBRATION_DOCS_LINK
            parent: The parent widget
        """
        super().__init__(parent=parent)

        self._url = url or CALIBRATION_DOCS_LINK
        link_text = text or "📚 Calibration Guide"

        # Set up the link appearance and behavior
        self.setText(
            f'<a href="{self._url}" style="color: #4a90e2; text-decoration: none;">{link_text}</a>'
        )
        self.setOpenExternalLinks(False)  # Handle the click ourselves for better control
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setToolTip("View calibration documentation and best practices")

        # Connect the link activation to the handler
        self.linkActivated.connect(self._open_calibration_docs)

    def _open_calibration_docs(self, url: str) -> None:
        """Open the calibration documentation in the default web browser."""
        QDesktopServices.openUrl(url=url)

    def set_url(self, url: str) -> None:
        """
        Update the URL that the link points to.

        Args:
            url: The new URL to use
        """
        self._url = url
        # Update the href in the label text
        current_text = self.text()
        # Extract the link text (everything between > and </a>)
        import re
        match = re.search(r'>(.*?)</a>', current_text)
        if match:
            link_text = match.group(1)
            self.setText(
                f'<a href="{self._url}" style="color: #4a90e2; text-decoration: none;">{link_text}</a>'
            )
