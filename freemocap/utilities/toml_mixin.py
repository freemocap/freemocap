"""TOML serialization mixin for Pydantic models.

Provides model_dump_toml / model_validate_toml methods that mirror
the Pydantic model_dump_json / model_validate_json interface.

Uses the ``toml`` package for reading and writing.
"""

from pathlib import Path
from typing import Self

import numpy as np
import toml
from pydantic import BaseModel


def numpy_to_python(obj: object) -> object:
    """Recursively convert numpy types to native Python types for TOML."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, dict):
        return {k: numpy_to_python(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [numpy_to_python(v) for v in obj]
    if isinstance(obj, tuple):
        return [numpy_to_python(v) for v in obj]
    return obj


class TomlMixin:
    """Mixin that adds TOML serialization to Pydantic BaseModel subclasses.

    Add as a base class alongside BaseModel:
        class MyModel(BaseModel, TomlMixin): ...
    """

    def model_dump_toml(self: BaseModel) -> str:
        """Serialize model to a TOML string."""
        data = self.model_dump(mode="python")
        data = numpy_to_python(data)
        return toml.dumps(data)

    def model_dump_toml_file(self: BaseModel, path: Path) -> None:
        """Serialize model to a TOML file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_toml())

    @classmethod
    def model_validate_toml(cls, toml_string: str) -> Self:
        """Deserialize model from a TOML string."""
        data = toml.loads(toml_string)
        return cls.model_validate(data)

    @classmethod
    def model_validate_toml_file(cls, path: Path) -> Self:
        """Deserialize model from a TOML file."""
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"TOML file not found: {path}")
        data = toml.load(path)
        return cls.model_validate(data)