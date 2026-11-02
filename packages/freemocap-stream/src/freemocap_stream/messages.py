"""Self-describing messages: one CBOR map per message, envelope first.

Every message starts with the envelope FreeMoCap clients validate (kind, version,
timestamp, sequence) and continues with its payload fields in order. A message
carries everything needed to interpret it, so no client depends on an earlier one.
The encoding matches FreeMoCap's own (freemocap/core/streaming/message_model.py).
"""
from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any

import cbor2
import numpy as np

ENVELOPE_FIELDS = ("kind", "version", "timestamp", "sequence")


def encode_message(
    kind: str,
    payload: Mapping[str, Any] | None = None,
    *,
    timestamp: float = 0.0,
    sequence: int = 0,
    version: int = 0,
) -> bytes:
    """Encode one message: the envelope, then every payload field that is not None.

    Payload values are maps, lists, strings, numbers, booleans and bytes; byte-like
    views are copied into bytes. Numerical arrays travel as channel blocks
    (`freemocap_stream.frames.channel_block`), never as nested lists.
    """
    if not kind:
        raise ValueError("A message needs a kind")
    if version < 0 or sequence < 0:
        raise ValueError("Message version and sequence must be nonnegative")
    message: dict[str, Any] = {
        "kind": kind,
        "version": int(version),
        "timestamp": float(timestamp),
        "sequence": int(sequence),
    }
    for key, value in (payload or {}).items():
        if key in ENVELOPE_FIELDS:
            raise ValueError(f"Payload field {key!r} would replace the envelope")
        if value is not None:
            message[key] = _wire_value(value)
    return cbor2.dumps(message)


def _wire_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bytes)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (bytearray, memoryview)):
        return bytes(value)
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        raise TypeError("Send numerical arrays as channel blocks, not nested lists")
    if isinstance(value, Mapping):
        return {key: _wire_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_wire_value(item) for item in value]
    raise TypeError(f"Cannot encode {type(value).__name__} in a stream message")
