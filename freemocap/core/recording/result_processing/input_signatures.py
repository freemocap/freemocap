"""Deterministic fingerprints of scientific definitions and numeric stage inputs."""

from dataclasses import dataclass
from enum import Enum
import hashlib
import json

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel


def _signature_value(value: object) -> object:
    if isinstance(value, BaseModel):
        return _signature_value(value.model_dump(mode="python"))
    if isinstance(value, Enum):
        return _signature_value(value.value)
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("Signature dictionaries require string keys")
        # Mapping evaluation and channel layout can depend on declaration order.
        return {key: _signature_value(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted(
            (_signature_value(item) for item in value),
            key=lambda item: json.dumps(item, allow_nan=False),
        )
    if isinstance(value, (tuple, list)):
        return [_signature_value(item) for item in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise TypeError(f"Unsupported signature value: {type(value).__name__}")


def definition_signature(value: object) -> str:
    payload = json.dumps(
        _signature_value(value),
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def point_array_signature(values: NDArray[np.float64]) -> str:
    """Hash shape, missingness and values independently of Parquet batching and NaN payloads."""
    digest = hashlib.sha256(str(values.shape).encode("ascii"))
    for start in range(0, len(values), 1024):
        block = np.array(
            values[start : start + 1024], dtype="<f8", order="C", copy=True
        )
        if np.isinf(block).any():
            raise ValueError("Point inputs cannot contain infinity")
        missing = np.isnan(block)
        block[missing] = 0.0
        digest.update(missing.tobytes(order="C"))
        digest.update(block.tobytes(order="C"))
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class ReconstructionInputSignatures:
    points: str
    model: str
    fit: str
    reconstruction: str
