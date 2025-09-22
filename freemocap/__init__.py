"""A free and open source markerless motion capture system for everyone 💀✨"""

__author__ = """Skelly FreeMoCap"""
__email__ = "info@freemocap.org"
__version__ = "v1.7.0"
__description__ = "A free and open source markerless motion capture system for everyone 💀✨"

__package_name__ = "freemocap"
__repo_url__ = f"https://github.com/freemocap/{__package_name__}/"
__repo_issues_url__ = f"{__repo_url__}issues"

from freemocap.system.logging_configuration.configure_logging import configure_logging
from freemocap.system.logging_configuration.log_levels import LogLevels

LOG_LEVEL = LogLevels.TRACE
configure_logging(LOG_LEVEL)

