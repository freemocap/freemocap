"""Anthropometric body-segment inertial parameters (BSIP).

Source: de Leva, P. (1996), "Adjustments to Zatsiorsky-Seluyanov's segment
inertia parameters," J. Biomechanics 29(9):1223-1230, Table 4 (primary
endpoints). Values are transcribed from that table and converted from percent
to fractions.

Per segment we store, as fractions of segment length (except mass, a fraction
of total body mass):
  - ``mass_fraction``      : segment mass / total body mass
  - ``com_fraction``       : CoM position from the proximal/cranial endpoint
  - ``k_sagittal``         : radius of gyration about the sagittal axis
  - ``k_transverse``       : radius of gyration about the transverse axis
  - ``k_longitudinal``     : radius of gyration about the longitudinal (long) axis

The segment inertia tensor about its own CoM, in the segment's principal frame,
is then ``J = mass * diag((k_sagittal*L)^2, (k_transverse*L)^2, (k_longitudinal*L)^2)``
where ``mass`` is the segment's absolute mass and ``L`` its length.

de Leva reports separate female and male tables. By default we use the mean of
the two (``DE_LEVA_MEAN`` / ``segment_inertial_parameters()``); the per-sex
tables remain available.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class SegmentInertialParameters:
    mass_fraction: float
    com_fraction: float
    k_sagittal: float
    k_transverse: float
    k_longitudinal: float

    def mean_with(self, other: "SegmentInertialParameters") -> "SegmentInertialParameters":
        return SegmentInertialParameters(
            mass_fraction=(self.mass_fraction + other.mass_fraction) / 2.0,
            com_fraction=(self.com_fraction + other.com_fraction) / 2.0,
            k_sagittal=(self.k_sagittal + other.k_sagittal) / 2.0,
            k_transverse=(self.k_transverse + other.k_transverse) / 2.0,
            k_longitudinal=(self.k_longitudinal + other.k_longitudinal) / 2.0,
        )


# de Leva 1996, Table 4, females (body mass 61.9 kg). Percent values / 100.
DE_LEVA_FEMALE: dict[str, SegmentInertialParameters] = {
    "head":      SegmentInertialParameters(0.0668, 0.5894, 0.330, 0.359, 0.318),
    "trunk":     SegmentInertialParameters(0.4257, 0.4151, 0.357, 0.339, 0.171),
    "upper_arm": SegmentInertialParameters(0.0255, 0.5754, 0.278, 0.260, 0.148),
    "forearm":   SegmentInertialParameters(0.0138, 0.4559, 0.261, 0.257, 0.094),
    "hand":      SegmentInertialParameters(0.0056, 0.7474, 0.531, 0.454, 0.335),
    "thigh":     SegmentInertialParameters(0.1478, 0.3612, 0.369, 0.364, 0.162),
    "shank":     SegmentInertialParameters(0.0481, 0.4416, 0.271, 0.267, 0.093),
    "foot":      SegmentInertialParameters(0.0129, 0.4014, 0.299, 0.279, 0.139),
}

# de Leva 1996, Table 4, males (body mass 73.0 kg). Percent values / 100.
DE_LEVA_MALE: dict[str, SegmentInertialParameters] = {
    "head":      SegmentInertialParameters(0.0694, 0.5976, 0.362, 0.376, 0.312),
    "trunk":     SegmentInertialParameters(0.4346, 0.4486, 0.372, 0.347, 0.191),
    "upper_arm": SegmentInertialParameters(0.0271, 0.5772, 0.285, 0.269, 0.158),
    "forearm":   SegmentInertialParameters(0.0162, 0.4574, 0.276, 0.265, 0.121),
    "hand":      SegmentInertialParameters(0.0061, 0.7900, 0.628, 0.513, 0.401),
    "thigh":     SegmentInertialParameters(0.1416, 0.4095, 0.329, 0.329, 0.149),
    "shank":     SegmentInertialParameters(0.0433, 0.4459, 0.255, 0.249, 0.103),
    "foot":      SegmentInertialParameters(0.0137, 0.4415, 0.257, 0.245, 0.124),
}

# Default: the mean of the female and male tables (computed, single source of truth).
DE_LEVA_MEAN: dict[str, SegmentInertialParameters] = {
    segment: DE_LEVA_FEMALE[segment].mean_with(DE_LEVA_MALE[segment])
    for segment in DE_LEVA_FEMALE
}


def segment_inertial_parameters(
    sex: Literal["mean", "female", "male"] = "mean",
) -> dict[str, SegmentInertialParameters]:
    """Return the de Leva BSIP table for the requested sex (default: the mean)."""
    if sex == "mean":
        return DE_LEVA_MEAN
    if sex == "female":
        return DE_LEVA_FEMALE
    if sex == "male":
        return DE_LEVA_MALE
    raise ValueError(f"sex must be 'mean', 'female', or 'male', got {sex!r}")
