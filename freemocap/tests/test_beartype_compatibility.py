"""Keep startup class decoration working when dependency versions change."""

import subprocess
import sys
import textwrap


def test_abstract_dataclass_with_self_return_annotation_decorates():
    # An isolated interpreter matches dependency import time, without pytest's
    # import hooks or previously decorated classes masking the regression.
    result = subprocess.run([sys.executable, "-B", "-c", textwrap.dedent("""
        from __future__ import annotations
        from abc import ABC, abstractmethod
        from dataclasses import dataclass
        from beartype import beartype

        @beartype
        @dataclass
        class Example(ABC):
            @classmethod
            @abstractmethod
            def create(cls, config: object) -> Example:
                ...

        print("DECORATION_OK")
    """)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "DECORATION_OK" in result.stdout
