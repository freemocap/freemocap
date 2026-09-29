"""Compatibility entry point; implementation lives outside the test suite."""
import sys
from freemocap.tools.datasets import preparation as _implementation

if __name__ == "__main__":
    _implementation.main()
else:
    sys.modules[__name__] = _implementation
