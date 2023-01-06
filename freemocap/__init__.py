import sys
from pathlib import Path

base_package_path = Path(__file__).parent.parent
print(f"adding base_package_path: {base_package_path} : to sys.path")
sys.path.insert(0, str(base_package_path))  # add par

from freemocap.configuration.logging.configure_logging import configure_logging

configure_logging()
