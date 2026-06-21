"""
Tunable configuration for the realtime filtering + skeleton-fitting stage.

Consumed by the realtime aggregator node, which wires these values into:
    - ``RealtimeKeypointFilter``  (One Euro smoothing of raw 3D keypoints)
    - ``RealtimePointGate``       (velocity teleportation rejection)
    - ``RealtimeSkeletonFitter``  (canonical FABRIK + online bone lengths)
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

    # ---- FABRIK params ----
    fabrik_tolerance: float = 0.1    # mm — settling threshold between iterations
    fabrik_max_iterations: int = 20

    # ---- Integral bone-length correction (PID-like I term) ----
    # Integral gain — how aggressively each frame's axial residual (mm)
    # contributes to the accumulated integral.  The integral directly
    # biases the bone length.  0 = no correction (pure Welford blending).
    # Higher = faster drift correction.  Typical: 0.03–0.15.
    integral_gain: float = 0.05

    # Per-frame retention factor for the integral accumulator.
    # 0.95 = 5% decay per frame → ~0.67 s time constant at 30 fps.
    # Higher (closer to 1) = longer memory, less steady-state error
    # but slower to release when the error vanishes.
    # Lower = faster decay, shorter memory.  Range: 0.80–0.99.
    integral_leak: float = 0.95

    # Hard clamp on the absolute integral value applied to any bone
    # length (mm).  Prevents a single bone from being biased by more
    # than this amount regardless of accumulated error.  Also serves
    # as anti-windup for the integrator.
    max_integral_correction_mm: float = 50.0

    # ---- Within-frame FABRIK refinement (escapes coupled-bone local minima) ----
    # Number of extra FABRIK solves per frame with nudged bone lengths.
    # 0 = disabled (fastest).  1-2 recommended.  Each pass is cheap
    # (~3-5 FABRIK iterations on warm-started positions).
    fabrik_refinement_passes: int = 2

    # Within-frame bone-length adjustment gain.  Higher than integral_gain
    # because this is per-frame (no temporal smoothing).  Default 0.3.
    fabrik_refinement_gain: float = 0.3

    # Stddev of Gaussian jitter added to bone lengths on the final
    # refinement pass (mm).  Helps escape local minima that deterministic
    # gradient-following can't.  0 = deterministic only.  Default 3.0.
    fabrik_jitter_mm: float = 3.0

    # ---- Welford estimator staleness prevention ----
    # Maximum effective sample count for the online bone-length estimator.
    # Beyond this, the update switches from cumulative mean (where each
    # new frame's weight approaches zero) to a constant-weight EMA update,
    # preventing the estimator from becoming arbitrarily resistant to
    # change during long recordings.  Default 300 = ~10 s at 30 fps.
    max_welford_samples: int = 300

    # ---- Subject scale ----
    # Subject standing height in keypoint-coordinate units (mm). The charuco
    # calibration produces mm-scale coordinates, so the bone-length seeds (which
    # scale by height) use the same units as observed inter-keypoint distances.
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
