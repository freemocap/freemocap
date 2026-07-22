"""
Tunable configuration for the realtime filtering + skeleton-fitting stage.

Consumed by the realtime aggregator node, which wires these values into:
    - ``RealtimeKeypointFilter``  (One Euro smoothing of raw 3D keypoints)
    - ``RealtimePointGate``       (velocity teleportation rejection)
    - ``RealtimeSkeletonRigidifier``  (rigid-body skeleton correction)
    - triangulation               (reprojection-error gating)
"""

from pydantic import BaseModel


class RealtimeFilterConfig(BaseModel):
    """Tunable parameters for the realtime filtering pipeline.

    Coordinate-space assumptions
    ----------------------------
    Triangulated 3D positions arrive in **millimeters** (the charuco board
    used for calibration is defined with ``square_length_mm``, so the
    calibration extrinsics and all downstream triangulation output are in mm).

    The One Euro filter's adaptive cutoff formula is::

        cutoff(Hz) = min_cutoff + beta * |velocity(mm/s)|

    Because velocity is in mm/s, **beta has units of 1/mm**.  Tuning beta as
    if the data were in meters (i.e. ~0.3) will produce a filter that is
    ~1000x too responsive — passing nearly all noise through at any non-zero
    velocity.  The defaults here assume millimeter-space coordinates.
    """

    # ---- One Euro Filter ----
    # Minimum cutoff frequency (Hz) applied when the keypoint is stationary.
    # Goal: settle quickly when motion stops while suppressing static jitter.
    #
    #   adaptive cutoff(Hz) = min_cutoff + beta * |velocity_mm_s|
    #
    # Variable framerate is handled automatically — the filter uses actual elapsed
    # time (seconds) between calls, so behaviour is consistent at 15 fps or 60 fps.
    #
    # Settling time at ~30 fps (time to reach 97% of target after motion stops):
    #   0.1 Hz -> ~3.0 s  (heavy smoothing, floaty / dragged feel)
    #   0.5 Hz -> ~0.8 s
    #   1.0 Hz -> ~0.4 s  <- default, responsive settling
    #   2.0 Hz -> ~0.2 s  (light smoothing, more jitter visible)
    #   5.0 Hz -> ~0.1 s  (near pass-through)
    #
    # If the skeleton drags behind motion: raise min_cutoff (or raise beta).
    # If the skeleton jitters while still: lower min_cutoff.
    min_cutoff: float = 1.0

    # Speed coefficient (units: 1/mm).
    # Determines how quickly the effective cutoff rises with keypoint velocity.
    # Because positions are in millimetres, velocity is in mm/s and beta is in 1/mm.
    #
    #   cutoff(Hz) = min_cutoff + beta * |velocity_mm_s|
    #
    # IMPORTANT: beta is in units of 1/mm, NOT 1/m.
    # beta = 0.3 (meter-space convention) becomes 300 Hz at 1 m/s -> pass-through.
    # Appropriate range for mm-space mocap data: 0.003 - 0.02.
    #
    # Raise beta -> less lag during fast movement, more jitter during slow.
    # Lower beta -> more uniform smoothing regardless of speed.
    beta: float = 0.01

    # Cutoff frequency for the derivative (velocity-estimate) filter (Hz).
    # Lower = smoother velocity estimate -> cutoff adapts more gradually.
    # Higher = faster adaptation -> more responsive to sudden speed changes.
    d_cutoff: float = 1.0

    # ---- Rigid-body skeleton correction ----
    # Per bone, the online estimator keeps the best-K length measurements
    # (ranked by reprojection error, with an age decay) and enforces their
    # median via a single closed-form forward pass — the streaming analogue of
    # the posthoc rigid-bones step. No iteration, no convergence loop.

    # Best-K buffer size per bone. Larger = steadier estimate, slower to adapt.
    # ~64 samples at 30 fps is ~2 s of the best observations retained.
    segment_length_buffer_capacity: int = 64

    # Age-decay time constant (seconds) for the buffer's eviction score:
    #   effective_error = error * exp(age / decay_s)
    # Stale samples lose their slot to fresh decent ones, so the estimate keeps
    # adapting (never permanently frozen on old data).
    segment_length_decay_s: float = 30.0

    # Trust-region half-width (fraction of the seed length). A measured length
    # outside seed × (1 ± fit_ratio) — lower bound floored at 0.25 × seed — is
    # rejected outright, and reported estimates are clamped to the same band.
    # 0.0 = lengths locked to the seeds; 1.0 = up to double/half the seed.
    segment_length_fit_ratio: float = 0.2

    # Measurements a bone's buffer must retain before its median may replace
    # the seed. Bootstrap protection: one frame teaches nothing.
    segment_length_min_samples: int = 5

    # Max relative MAD (median absolute deviation / median) across a buffer's
    # retained samples for them to count as agreeing. A flickering or bimodal
    # measurement stream never replaces the seed.
    segment_length_agreement_tol: float = 0.05

    # Reprojection-error gate for admitting a length measurement (pixels).
    # Distinct from the triangulation survival gate below: a point may survive
    # triangulation yet be too sloppy to teach bone lengths.
    segment_length_max_reprojection_error_px: float = 15.0

    # ---- Segment-fit calibration ritual ----
    # "Reset skeleton fit" arms this ritual instead of re-fitting instantly:
    # countdown (subject gets into view) → quality-gated capture window →
    # freeze (captured lengths re-anchor the trust regions) → bounded drift.

    # Seconds between arming a refit and the capture window opening.
    calibration_countdown_s: float = 3.0

    # Fraction of measurable body keypoints that must be really observed (not
    # extrapolated) for a capture frame to count as good.
    calibration_capture_min_visible_fraction: float = 0.8

    # Max mean reprojection error across measured body keypoints for a capture
    # frame to count as good (pixels).
    calibration_capture_max_mean_error_px: float = 10.0

    # Consecutive good frames required to freeze the capture. ~1 s at 30 fps.
    calibration_capture_consecutive_good_frames: int = 30

    # Lower visibility floor for a capture frame to still teach the bones it
    # can see (per-bone buffers only sample really-observed endpoints, so a
    # partial body — seated at a desk, legs under the table — calibrates its
    # visible bones even though the full-body "good" gate never passes).
    calibration_capture_update_min_visible_fraction: float = 0.25

    # Max seconds in the capture window before a best-effort freeze: whatever
    # bones reached agreement are re-anchored; if none did, the ritual drops
    # back to normal live fitting. Bounds the ritual so it always terminates.
    calibration_capture_timeout_s: float = 15.0

    # ---- Subject scale ----
    # Subject standing height in keypoint-coordinate units (mm). The charuco
    # calibration produces mm-scale coordinates, so the bone-length seeds
    # (which scale by height) use the same units.
    height_mm: float = 1750.0

    # ---- Triangulation reprojection gate ----
    # Reject triangulated points whose mean reprojection error across cameras
    # exceeds this threshold (pixels). Higher = more permissive.
    max_reprojection_error_px: float = 60.0

    # ---- Velocity gate ----
    # Reject points that jump faster than this. Positions are in mm so velocity
    # is in mm/s. 50000 mm/s = 50 m/s — well above any human motion, but noisy
    # triangulation can produce brief spikes. Keep generous to avoid rejecting
    # real fast motions.
    max_velocity_mm_per_s: float = 50000.0

    # After this many consecutive rejections, accept unconditionally to prevent
    # permanent lockout. Lower = recover faster.
    max_rejected_streak: int = 5
