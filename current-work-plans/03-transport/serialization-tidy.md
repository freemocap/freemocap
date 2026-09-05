# On-disk serialization

Status: part of the posthoc rebuild, 2026-09-05.

The implementation target is [Recording data model](recording-data-model-proposal.md).
The execution/persistence plan is [Posthoc rebuild](../02-pipeline/posthoc-rebuild.md).

Row grain: one scalar component per group-local sample, source, reference frame, channel and run.
Timestamp is the primary cross-system temporal coordinate. The schema preserves the existing
self-describing channel/SkellyForge structure, with component/value for vectors, quaternions and
scalars. All sample timing lives in the same Parquet.

Core serialization and stage reprocessing precede optional CSV/NPY/Blender/.freemocap.mp4 exporters.
