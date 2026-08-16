from __future__ import annotations

from typing import Any

from freemocap.__main__ import _ensure_utf8_standard_stream


class ReconfigurableStream:
    def __init__(self) -> None:
        self.options: dict[str, Any] = {}

    def reconfigure(self, **kwargs: Any) -> None:
        self.options = kwargs


def test_standard_stream_is_reconfigured_for_utf8() -> None:
    stream = ReconfigurableStream()

    result = _ensure_utf8_standard_stream(stream)

    assert result is stream
    assert stream.options == {"encoding": "utf-8", "errors": "backslashreplace"}
