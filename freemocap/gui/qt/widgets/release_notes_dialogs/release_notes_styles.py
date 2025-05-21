"""
Stylesheet definitions for the release notes dialogs.
Provides both light and dark mode styles.
"""

class ReleaseNotesStyles:
    """
    Provides stylesheets for the release notes dialogs in both light and dark modes.
    """
    
    @staticmethod
    def get_dialog_style(dark_mode: bool = True) -> str:
        """Return the CSS style for the dialog."""
        if dark_mode:
            return """
                QDialog {
                    background-color: #1e1e1e;
                }
                QLabel {
                    color: #e0e0e0;
                }
                QRadioButton {
                    color: #c0c0c0;
                    font-size: 13px;
                    spacing: 8px;
                }
                QRadioButton::indicator {
                    width: 16px;
                    height: 16px;
                }
            """
        else:
            return """
                QDialog {
                    background-color: #f8f9fa;
                }
                QLabel {
                    color: #212529;
                }
                QRadioButton {
                    color: #495057;
                    font-size: 13px;
                    spacing: 8px;
                }
                QRadioButton::indicator {
                    width: 16px;
                    height: 16px;
                }
            """
        
    @staticmethod
    def get_tab_widget_style(dark_mode: bool = True) -> str:
        """Return the CSS style for the tab widget."""
        if dark_mode:
            return """
                QTabWidget::pane {
                    border: 1px solid #3a3a3a;
                    border-radius: 5px;
                    background-color: #2d2d2d;
                }
                QTabBar::tab {
                    background-color: #383838;
                    border: 1px solid #3a3a3a;
                    border-right: none;
                    border-top-left-radius: 4px;
                    border-bottom-left-radius: 4px;
                    padding: 10px 15px;
                    margin-bottom: 2px;
                    min-height: 25px;
                    min-width: 150px;
                    text-align: left;
                    color: #c0c0c0;
                }
                QTabBar::tab:selected {
                    background-color: #2d2d2d;
                    border-right: 1px solid #2d2d2d;
                    color: #ffffff;
                    font-weight: bold;
                    border-top: 3px solid #3498db;  /* Blue accent border */
                    border-left: 1px solid #3498db;  /* Blue accent border */
                    border-right: 1px solid #3498db;  /* Blue accent border */
                    border-bottom: 1px solid #3498db;  /* Blue accent border */
                }
                QTabBar::tab:hover:!selected {
                    background-color: #454545;
                }
                /* This is the key part for horizontal text in vertical tabs */
                QTabBar::tab:left {
                    margin-right: 2px;
                }
            """
        else:
            return """
                QTabWidget::pane {
                    border: 1px solid #d0d0d0;
                    border-radius: 5px;
                    background-color: #ffffff;
                }
                QTabBar::tab {
                    background-color: #f0f0f0;
                    border: 1px solid #d0d0d0;
                    border-right: none;
                    border-top-left-radius: 4px;
                    border-bottom-left-radius: 4px;
                    padding: 10px 15px;
                    margin-bottom: 2px;
                    min-height: 25px;
                    min-width: 150px;
                    text-align: left;
                }
                QTabBar::tab:selected {
                    background-color: #ffffff;
                    border-right: 1px solid #ffffff;
                    font-weight: bold;
                    border-left: 3px solid #3498db;  /* Blue accent border */
                }
                QTabBar::tab:hover:!selected {
                    background-color: #e0e0e0;
                }
                /* This is the key part for horizontal text in vertical tabs */
                QTabBar::tab:left {
                    margin-right: 2px;
                }
            """
    @staticmethod
    def get_group_box_style(dark_mode: bool = True) -> str:
        """Return the CSS style for group boxes."""
        if dark_mode:
            return """
                QGroupBox {
                    font-weight: bold;
                    border: 1px solid #3a3a3a;
                    border-radius: 5px;
                    margin-top: 10px;
                    padding-top: 15px;
                    color: #e0e0e0;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }
            """
        else:
            return """
                QGroupBox {
                    font-weight: bold;
                    border: 1px solid #d0d0d0;
                    border-radius: 5px;
                    margin-top: 10px;
                    padding-top: 15px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }
            """
    
    @staticmethod
    def get_button_style(dark_mode: bool = True) -> str:
        """Return the CSS style for buttons."""
        if dark_mode:
            return """
                QPushButton {
                    background-color: #2980b9;
                    color: white;
                    border-radius: 5px;
                    border: 1px solid #2980b9;
                    padding: 10px 25px;
                    font-weight: bold;
                    min-width: 120px;
                }
                QPushButton:hover {
                    background-color: #3498db;
                }
            """
        else:
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
    
    @staticmethod
    def get_html_content_style(dark_mode: bool = True) -> str:
        """Return the CSS style for HTML content."""
        if dark_mode:
            return """
            <style>
            body { color: #e0e0e0; }
            a { color: #5dade2; text-decoration: none; font-weight: 500; }
            .feature { color: #2ecc71; font-weight: bold; }
            </style>
            """
        else:
            return """
            <style>
            a { color: #2980b9; text-decoration: none; font-weight: 500; }
            .feature { color: #27ae60; font-weight: bold; }
            </style>
            """