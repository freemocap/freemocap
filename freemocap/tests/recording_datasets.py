"""Compatibility entry point; implementation lives outside the test suite."""
import sys
from freemocap.tools.datasets import catalog as _implementation

sys.modules[__name__] = _implementation
