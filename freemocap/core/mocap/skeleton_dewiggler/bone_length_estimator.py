"""
Online bone length estimation with anthropometric priors.

Starts from standard body proportions (scaled by height) and adapts
toward observed data as confidence builds. Handles the noise-inflated
distance bias that occurs when both bone endpoints have position noise.

Key insight: adding Gaussian noise to both endpoints of a bone
systematically inflates the observed Euclidean distance (Rice distribution).
The bias is approximately (n_dims - 1) * sigma² / (2 * d), which is
negligible for long bones (~0.03cm for a 43cm thigh) but significant for
short bones (~7% for a 4cm heel). We apply a first-order correction.

Usage:
    from skeleton_config import SkeletonDefinition
    from bone_length_estimator import AnthropometricPrior, BoneLengthEstimator

    skeleton = SkeletonDefinition.mediapipe_body()
    prior = AnthropometricPrior.mediapipe_body()

    estimator = BoneLengthEstimator.create(
        skeleton=skeleton,
        prior=prior,
        height_meters=1.75,
        noise_sigma=0.008,  # per-keypoint position noise (meters)
    )

    for positions in stream:
        estimator.observe(positions=positions)
        lengths = estimator.current_lengths    # blended estimates
        confidence = estimator.current_confidence  # per-bone 0→1

    # Wire into the filter pipeline:
    pipeline = SkeletonFilterPipeline.from_bone_lengths(
        skeleton=skeleton,
        config=filter_config,
        bone_lengths=estimator.current_lengths,
    )
"""

from collections import deque
from dataclasses import dataclass, field

import numpy as np
from pydantic import BaseModel, ConfigDict, model_validator

from mediapipe_skeleton_config import SkeletonDefinition


# ============================================================
# Single Bone Estimate
# ============================================================


@dataclass(frozen=True)
class BoneLengthEstimate:
    """Snapshot of a single bone's current length estimate."""

    bone_key: str
    prior_length: float
    raw_median: float | None
    corrected_median: float | None
    observed_iqr: float | None
    sample_count: int
    confidence: float
    blended_length: float


# ============================================================
# Anthropometric Prior
# ============================================================


class AnthropometricPrior(BaseModel):
    """
    Standard body proportions as bone-length-to-height ratios.

    Each ratio maps a bone key ("parent->child") to
    ``bone_length / total_height``.
    """

    model_config = ConfigDict(frozen=True)

    ratios: dict[str, float]

    @model_validator(mode="after")
    def _validate_positive(self) -> "AnthropometricPrior":
        for key, ratio in self.ratios.items():
            if ratio <= 0.0:
                raise ValueError(f"Ratio for '{key}' must be positive, got {ratio}")
        return self

    def to_bone_lengths(self, *, height_meters: float) -> dict[str, float]:
        """Scale ratios by total body height to get bone lengths in meters."""
        if height_meters <= 0.0:
            raise ValueError(f"height_meters must be positive, got {height_meters}")
        return {key: ratio * height_meters for key, ratio in self.ratios.items()}

    # --------------------------------------------------------
    # Mediapipe Body
    # --------------------------------------------------------

    @classmethod
    def mediapipe_body(cls) -> "AnthropometricPrior":
        """
        Standard adult body proportions.

        Ratios from Winter (2009) and Drillis & Contini (1966),
        expressed as bone_length / total_standing_height.
        """
        return cls(ratios={
            # Arms
            "left_shoulder->left_elbow": 0.186,
            "left_elbow->left_wrist": 0.146,
            "right_shoulder->right_elbow": 0.186,
            "right_elbow->right_wrist": 0.146,
            # Legs
            "left_hip->left_knee": 0.245,
            "left_knee->left_ankle": 0.246,
            "right_hip->right_knee": 0.245,
            "right_knee->right_ankle": 0.246,
            # Feet
            "left_ankle->left_heel": 0.024,
            "left_ankle->left_foot_index": 0.085,
            "right_ankle->right_heel": 0.024,
            "right_ankle->right_foot_index": 0.085,
        })

    # --------------------------------------------------------
    # Mediapipe Hands
    # --------------------------------------------------------

    @classmethod
    def _mediapipe_hand(cls, *, side: str) -> "AnthropometricPrior":
        """
        Standard adult hand proportions.

        Hand length ~ 0.108 * height. Finger segment ratios from
        Buryanov & Kotiuk (2010) and Garrett (1971), expressed
        as bone_length / total_standing_height.
        """
        if side not in ("left", "right"):
            raise ValueError(f"side must be 'left' or 'right', got '{side}'")

        prefix = f"{side}_hand"

        def bk(parent: str, child: str) -> str:
            return f"{prefix}_{parent}->{prefix}_{child}"

        hl = 0.108  # hand_length / height

        return cls(ratios={
            # Thumb
            bk("wrist", "thumb_cmc"): hl * 0.15,
            bk("thumb_cmc", "thumb_mcp"): hl * 0.18,
            bk("thumb_mcp", "thumb_ip"): hl * 0.17,
            bk("thumb_ip", "thumb_tip"): hl * 0.14,
            # Index
            bk("wrist", "index_finger_mcp"): hl * 0.48,
            bk("index_finger_mcp", "index_finger_pip"): hl * 0.26,
            bk("index_finger_pip", "index_finger_dip"): hl * 0.15,
            bk("index_finger_dip", "index_finger_tip"): hl * 0.12,
            # Middle
            bk("wrist", "middle_finger_mcp"): hl * 0.46,
            bk("middle_finger_mcp", "middle_finger_pip"): hl * 0.28,
            bk("middle_finger_pip", "middle_finger_dip"): hl * 0.17,
            bk("middle_finger_dip", "middle_finger_tip"): hl * 0.13,
            # Ring
            bk("wrist", "ring_finger_mcp"): hl * 0.44,
            bk("ring_finger_mcp", "ring_finger_pip"): hl * 0.26,
            bk("ring_finger_pip", "ring_finger_dip"): hl * 0.15,
            bk("ring_finger_dip", "ring_finger_tip"): hl * 0.12,
            # Pinky
            bk("wrist", "pinky_mcp"): hl * 0.42,
            bk("pinky_mcp", "pinky_pip"): hl * 0.22,
            bk("pinky_pip", "pinky_dip"): hl * 0.12,
            bk("pinky_dip", "pinky_tip"): hl * 0.10,
        })

    @classmethod
    def mediapipe_left_hand(cls) -> "AnthropometricPrior":
        return cls._mediapipe_hand(side="left")

    @classmethod
    def mediapipe_right_hand(cls) -> "AnthropometricPrior":
        return cls._mediapipe_hand(side="right")

    # --------------------------------------------------------
    # Merge
    # --------------------------------------------------------

    @classmethod
    def merge(cls, *, priors: list["AnthropometricPrior"]) -> "AnthropometricPrior":
        """Merge multiple priors. Raises on duplicate bone keys."""
        merged: dict[str, float] = {}
        for prior in priors:
            for key, ratio in prior.ratios.items():
                if key in merged:
                    raise ValueError(f"Duplicate bone key '{key}' when merging priors")
                merged[key] = ratio
        return cls(ratios=merged)

    @classmethod
    def mediapipe_body_and_hands(cls) -> "AnthropometricPrior":
        """Body + both hands merged."""
        return cls.merge(priors=[
            cls.mediapipe_body(),
            cls.mediapipe_left_hand(),
            cls.mediapipe_right_hand(),
        ])


# ============================================================
# Estimator Config
# ============================================================


class EstimatorConfig(BaseModel):
    """Tunable parameters for bone length estimation."""

    model_config = ConfigDict(frozen=True)

    max_samples: int = 500
    min_samples_for_full_confidence: int = 100
    iqr_confidence_sensitivity: float = 10.0


# ============================================================
# Noise Bias Correction
# ============================================================

_N_SPATIAL_DIMS: int = 3


def _correct_noise_bias(
    *,
    raw_median: float,
    noise_sigma: float,
) -> float:
    """
    First-order correction for the noise-inflated distance bias.

    When both endpoints of a bone have i.i.d. Gaussian position noise
    with std ``noise_sigma`` per axis, the observed Euclidean distance
    follows a Rice distribution whose mean is biased upward.

    The first-order correction is:
        d_corrected ≈ d_observed - (n-1) * sigma_diff² / (2 * d_observed)
    where:
        n = number of spatial dimensions (3)
        sigma_diff² = 2 * noise_sigma²  (independent noise on both endpoints)

    This is accurate when d >> sigma. For very short bones where
    d ~ sigma, the correction can overshoot, so we clamp to a minimum
    of ``noise_sigma`` (below which we have no real signal anyway).
    """
    if raw_median <= 0.0:
        return raw_median

    sigma_diff_sq = 2.0 * noise_sigma ** 2
    correction = (_N_SPATIAL_DIMS - 1) * sigma_diff_sq / (2.0 * raw_median)
    corrected = raw_median - correction

    # Don't let correction push below noise floor
    return max(corrected, noise_sigma)


# ============================================================
# Bone Length Estimator
# ============================================================


@dataclass
class BoneLengthEstimator:
    """
    Online bone length estimator with anthropometric priors.

    Per bone, maintains a rolling buffer of observed inter-keypoint
    distances. Blends between the anthropometric prior and the
    bias-corrected observed median based on a confidence score.

    Confidence accounts for:
        - Sample count: more data → higher confidence
        - Measurement consistency: tighter IQR → higher confidence

    Confidence formula:
        count_factor = clamp(n / min_samples, 0, 1)
        consistency_factor = 1 / (1 + sensitivity * iqr / median)
        confidence = count_factor * consistency_factor

    Blended estimate:
        length = prior * (1 - confidence) + corrected_median * confidence
    """

    skeleton: SkeletonDefinition
    config: EstimatorConfig
    prior_lengths: dict[str, float]
    noise_sigma: float
    _observations: dict[str, deque[float]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        for bone in self.skeleton.bones:
            if bone.key not in self.prior_lengths:
                raise ValueError(f"Missing prior length for bone '{bone.key}'")
            if self.prior_lengths[bone.key] <= 0.0:
                raise ValueError(
                    f"Prior length must be positive for '{bone.key}', "
                    f"got {self.prior_lengths[bone.key]}"
                )
        if self.noise_sigma < 0.0:
            raise ValueError(f"noise_sigma must be non-negative, got {self.noise_sigma}")

        self._observations = {
            bone.key: deque(maxlen=self.config.max_samples)
            for bone in self.skeleton.bones
        }

    @classmethod
    def create(
        cls,
        *,
        skeleton: SkeletonDefinition,
        prior: AnthropometricPrior,
        height_meters: float,
        noise_sigma: float,
        config: EstimatorConfig = EstimatorConfig(),
    ) -> "BoneLengthEstimator":
        """
        Create estimator from skeleton + anthropometric prior + height.

        Args:
            skeleton: skeleton topology (bones define what to measure).
            prior: anthropometric ratios for bone lengths.
            height_meters: subject's standing height in meters.
            noise_sigma: estimated per-keypoint position noise std (meters).
                         Can be calibrated from a static capture.
            config: estimation parameters.
        """
        prior_lengths = prior.to_bone_lengths(height_meters=height_meters)

        for bone in skeleton.bones:
            if bone.key not in prior_lengths:
                raise ValueError(
                    f"Anthropometric prior missing bone '{bone.key}'. "
                    f"Prior covers: {sorted(prior_lengths.keys())}"
                )

        return cls(
            skeleton=skeleton,
            config=config,
            prior_lengths=prior_lengths,
            noise_sigma=noise_sigma,
        )

    def observe(self, *, positions: dict[str, np.ndarray]) -> None:
        """
        Observe one frame of keypoint positions.

        Bones where either endpoint is missing are silently skipped.
        """
        for bone in self.skeleton.bones:
            parent_pos = positions.get(bone.parent)
            child_pos = positions.get(bone.child)
            if parent_pos is None or child_pos is None:
                continue

            dist = float(np.linalg.norm(
                np.asarray(parent_pos) - np.asarray(child_pos)
            ))
            if dist <= 0.0:
                continue

            self._observations[bone.key].append(dist)

    def get_estimate(self, *, bone_key: str) -> BoneLengthEstimate:
        """Get the current blended estimate for a single bone."""
        if bone_key not in self._observations:
            raise ValueError(f"Unknown bone '{bone_key}'")

        prior_length = self.prior_lengths[bone_key]
        obs = self._observations[bone_key]
        n = len(obs)

        if n == 0:
            return BoneLengthEstimate(
                bone_key=bone_key,
                prior_length=prior_length,
                raw_median=None,
                corrected_median=None,
                observed_iqr=None,
                sample_count=0,
                confidence=0.0,
                blended_length=prior_length,
            )

        sorted_obs = np.array(sorted(obs))
        raw_median = float(np.median(sorted_obs))
        q25 = float(np.percentile(sorted_obs, 25))
        q75 = float(np.percentile(sorted_obs, 75))
        iqr = q75 - q25

        corrected_median = _correct_noise_bias(
            raw_median=raw_median,
            noise_sigma=self.noise_sigma,
        )

        # Confidence = count_factor * consistency_factor
        count_factor = min(1.0, n / self.config.min_samples_for_full_confidence)

        if raw_median > 1e-9:
            normalized_iqr = iqr / raw_median
        else:
            normalized_iqr = float("inf")

        consistency_factor = 1.0 / (
            1.0 + self.config.iqr_confidence_sensitivity * normalized_iqr
        )

        confidence = count_factor * consistency_factor
        blended = prior_length * (1.0 - confidence) + corrected_median * confidence

        return BoneLengthEstimate(
            bone_key=bone_key,
            prior_length=prior_length,
            raw_median=raw_median,
            corrected_median=corrected_median,
            observed_iqr=iqr,
            sample_count=n,
            confidence=confidence,
            blended_length=blended,
        )

    @property
    def current_lengths(self) -> dict[str, float]:
        """Current blended bone length estimates for all bones."""
        return {
            bone.key: self.get_estimate(bone_key=bone.key).blended_length
            for bone in self.skeleton.bones
        }

    @property
    def current_confidence(self) -> dict[str, float]:
        """Current confidence (0→1) for all bones."""
        return {
            bone.key: self.get_estimate(bone_key=bone.key).confidence
            for bone in self.skeleton.bones
        }

    @property
    def all_estimates(self) -> dict[str, BoneLengthEstimate]:
        """Full estimate details for all bones."""
        return {
            bone.key: self.get_estimate(bone_key=bone.key)
            for bone in self.skeleton.bones
        }
