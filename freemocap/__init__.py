"""A free and open source markerless motion capture system for everyone 💀✨"""

__author__ = """Skelly FreeMoCap"""
__email__ = "info@freemocap.org"
__version__ = "v1.0.31"
__description__ = "A free and open source markerless motion capture system for everyone 💀✨"

__package_name__ = "freemocap"
__repo_url__ = f"https://github.com/freemocap/{__package_name__}/"
__repo_issues_url__ = f"{__repo_url__}issues"


from freemocap.system.logging.configure_logging import configure_logging, LogLevel

configure_logging(LogLevel.TRACE)
import logging

logger = logging.getLogger(__name__)
logger.info(f"Initializing {__package_name__} package, version: {__version__}, from file: {__file__}")
