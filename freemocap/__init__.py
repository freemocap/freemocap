"""Top-level package for freemocap"""

__author__ = """Skelly FreeMoCap"""
__email__ = "info@freemocap.org"
__version__ = "v2023.01.1000"
__description__ = (
    "A free and open source markerless motion capture system for everyone 💀✨"
)
__package_name__ = "freemocap"
__repo_url__ = f"https://github.com/freemocap/{__package_name__}/"
__repo_issues_url__ = f"{__repo_url__}issues"


import sys
from pathlib import Path

base_package_path = Path(__file__).parent.parent
print(f"adding base_package_path: {base_package_path} : to sys.path")
sys.path.insert(0, str(base_package_path))  # add par

from freemocap.configuration.logging.configure_logging import configure_logging

configure_logging()
