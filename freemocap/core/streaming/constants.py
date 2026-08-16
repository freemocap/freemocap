"""Streaming-wide constants — a dependency-free leaf module.

Kept free of package imports so modules that need the nominal subject height can
import it without pulling the pubsub / realtime-config tree (which would
circularly import this constant).
"""

# Nominal subject height (mm) used to convert each segment's ``length_ratio``
# (a fraction of standing height) into an absolute rest length. Single source
# shared by the model's rest-pose build, the realtime aggregator, the
# RealtimeFilterConfig ``height_mm`` default, and the skeleton rigidifier's
# length seeds.
NOMINAL_SUBJECT_HEIGHT_MM = 1750.0
