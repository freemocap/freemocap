"""Streaming-wide constants — a leaf module OUTSIDE the ``standard_stream`` package.

Deliberately not inside ``standard_stream/``: importing anything from that
package runs its ``__init__``, which pulls the pubsub tree — and the pubsub
tree imports the realtime configs, which need this constant. Importing the
package to get a constant is exactly the circular import
(``pubsub_topics → realtime_pipeline_config → … → realtime_filter_config →
standard_stream``).
"""

# Nominal subject height (mm) used to convert each segment's ``length_ratio``
# (a fraction of standing height) into an absolute rest length. Single source
# shared by the schema's rest-pose build, the realtime aggregator, the
# RealtimeFilterConfig ``height_mm`` default, and the skeleton rigidifier's
# length seeds.
NOMINAL_SUBJECT_HEIGHT_MM = 1750.0
