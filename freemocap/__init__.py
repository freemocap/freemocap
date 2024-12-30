"""A free and open source markerless motion capture system for everyone 💀✨"""

__author__ = """Skelly FreeMoCap"""
__email__ = "info@freemocap.org"
__version__ = "v1.4.7"
__description__ = "A free and open source markerless motion capture system for everyone 💀✨"

__package_name__ = "freemocap"
__repo_url__ = f"https://github.com/freemocap/{__package_name__}/"
__repo_issues_url__ = f"{__repo_url__}issues"

import logging

from freemocap.system.logging_configuration.configure_logging import configure_logging
from freemocap.system.logging_configuration.log_test_messages import print_log_level_messages
from freemocap.system.logging_configuration.logger_builder import LogLevels
from freemocap.utilities.get_process_name import get_process_name

logger = logging.getLogger(__name__)
configure_logging(LogLevels.LOOP)

if get_process_name().lower() == "mainprocess":
    print_log_level_messages(logger)
logger.trace(f"Initializing {__package_name__} package, version: {__version__}, from file: {__file__}")
