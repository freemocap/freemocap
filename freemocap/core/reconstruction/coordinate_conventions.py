"""Bind calibration and reconstruction coordinates to Forge's authored conventions."""

from skellyforge.core.math.geometry.coordinate_systems.coordinate_system_registry import CoordinateSystemRegistry
from skellyforge.core.math.geometry.coordinate_systems.coordinate_system_transform import CoordinateSystemTransform

_REGISTRY = CoordinateSystemRegistry.from_default_yaml()

CALIBRATION_TO_RECONSTRUCTION = CoordinateSystemTransform(
    from_convention=_REGISTRY.get(name="ros"), to_convention=_REGISTRY.default,
)
RECONSTRUCTION_TO_CALIBRATION = CoordinateSystemTransform(
    from_convention=CALIBRATION_TO_RECONSTRUCTION.to_convention,
    to_convention=CALIBRATION_TO_RECONSTRUCTION.from_convention,
)
