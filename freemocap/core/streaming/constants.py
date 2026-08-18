"""Streaming-wide constants — a dependency-free leaf module.

Kept free of package imports so modules that need the nominal subject height can
import it without pulling the pubsub / realtime-config tree (which would
circularly import this constant).
"""

# Nominal subject height (mm) — the anthropometric seed for subject scaling
# (RealtimeFilterConfig's ``height_mm`` default).
NOMINAL_SUBJECT_HEIGHT_MM = 1750.0
