"""A free and open source markerless motion capture system for everyone 💀✨"""

__author__ = """Skelly FreeMoCap"""
__email__ = "info@freemocap.org"
__version__ = "v2.0.0-alpha.11"
__description__ = "A free and open source markerless motion capture system for everyone 💀✨"

__package_name__ = "freemocap"
__repo_url__ = f"https://github.com/freemocap/{__package_name__}/"
__repo_issues_url__ = f"{__repo_url__}issues"

from beartype.claw import beartype_this_package
beartype_this_package()

import time
tik = time.perf_counter()
from skellylogs import configure_logging, LogLevels

LOG_LEVEL = LogLevels.TRACE
configure_logging(LOG_LEVEL)

# Dump a Python traceback on native crashes (segfault / Windows access violation, e.g. 0xC0000005)
# instead of dying silently. Spawned workers re-import this package, so they inherit this too.
# Near-zero steady-state overhead — handlers stay dormant until a fatal signal actually fires.
import faulthandler
faulthandler.enable()
