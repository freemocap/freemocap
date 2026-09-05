"""Numeric expectations for the real-data pipeline tests.

Every "assumption number" the end-to-end pipeline tests assert against lives here as a
top-level constant, so it can be audited and tweaked in one place instead of hunted
through test bodies.

These are physical/anatomical invariants — a charuco solve is sub-pixel, a femur is not
two metres long, a body's centre of mass stays above the floor — NOT config-file values.
Editing a YAML does not change these. Each constant's comment records the value actually
measured on ``freemocap_test_data`` so the margin is visible at a glance.
"""

# --- the recording (3 synchronized videos, 7x5 charuco @ 58 mm square) ------------
EXPECTED_FRAME_COUNT = 222

# --- calibration solve quality -----------------------------------------------------
# Measured: reprojection_error_px = 0.359, n_observations_used = 666, rejected = 0.
MAX_REPROJECTION_ERROR_PX = 1.0
MIN_OBSERVATIONS_USED = 500
MAX_REJECTED_OBSERVATION_FRACTION = 0.05

# --- body reconstruction shape + coverage ------------------------------------------
# Provisional: the provisional posthoc output writes the hydrated SKELETON landmarks
# (124), not the old 27 tracked body keypoints. The final split is decided at the
# schema session, so this is expected to change.
EXPECTED_BODY_LANDMARK_COUNT = 124
MIN_FINITE_FRACTION = 0.9

# --- centre of mass sanity ----------------------------------------------------------
# Measured: total CoM z in [1495, 2397] mm.
COM_Z_MIN_MM = 500.0
COM_Z_MAX_MM = 3000.0

# --- segment lengths (median mm; measured value in each comment) --------------------
FEMUR_LENGTH_MM_RANGE = (250.0, 550.0)       # ~391
SHANK_LENGTH_MM_RANGE = (250.0, 500.0)       # ~375
UPPER_ARM_LENGTH_MM_RANGE = (200.0, 400.0)   # ~288
FOREARM_LENGTH_MM_RANGE = (150.0, 350.0)     # ~248
# left/right bones should agree within this relative fraction (measured < 2.5%).
BILATERAL_LENGTH_TOLERANCE = 0.05

# --- fitted subject scale (stature) -------------------------------------------------
PLAUSIBLE_BODY_HEIGHT_MM_RANGE = (1400.0, 2100.0)
