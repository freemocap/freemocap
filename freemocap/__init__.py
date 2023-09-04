"""Top-level package for freemocap"""

__author__ = """Skelly FreeMoCap"""
__email__ = "info@freemocap.org"
__version__ = "v1.0.21-rc"
__description__ = "A free and open source markerless motion capture system for everyone 💀✨"

__package_name__ = "freemocap"
__repo_url__ = f"https://github.com/freemocap/{__package_name__}/"
__repo_issues_url__ = f"{__repo_url__}issues"


# if we're running from source, we need to add the parent directory to sys.path
# import sys
# from pathlib import Path

#
# base_package_path = Path(__file__).parent.parent
# print(f"adding base_package_path: {base_package_path} : to sys.path")
# sys.path.insert(0, str(base_package_path))  # add par

from freemocap.system.logging.configure_logging import configure_logging

configure_logging()
import logging

logger = logging.getLogger(__name__)
logger.info(f"Initializing {__package_name__} package, version: {__version__}, from file: {__file__}")


# breadcrumbs for legacy/deprecated 'pre-alpha` entry point
def RunMe(*args, **kwargs):
    logger.info(
        "User tried using `pre-alpha` entry point (`import freemocap: freemocap.RunMe() - displaying friendly message then re-directing to `freemocap.__main__:main()` entry point"
    )

    print(
        "--------------------------------\n"
        "--------------------------------\n"
        "--------------------------------\n"
        "Hello! Looks like you're trying to use the `pre-alpha` entry point for FreeMoCap.\n"
        "This entry point is deprecated, so we're launching the GUI via `freemocap.__main__:main()` entry point.\n"
        "if you need to install the `pre-alpha` code, use `pip install freemocap==0.0.54`"
        "Thank you for using FreeMoCap!\n"
        "--------------------------------\n"
        "--------------------------------\n"
        "(NOTE  - this entry point will be removed eventually\n"
        "--------------------------------\n"
    )

    from freemocap.__main__ import main

    main()
