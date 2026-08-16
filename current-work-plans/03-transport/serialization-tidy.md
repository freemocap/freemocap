# On-Disk Serialization (tidy-long format)

> **Scaffold (2026-08-14) — needs a source-read pass before full prose.** Carried from the archived spec.

**Describes (target):** the on-disk form of recorded reconstruction — tidy-long CSV/parquet vs. the
skellyforge parquet schema.
**Salvage:** [`archive/streaming-compatibility-specs/10-serialization-and-tidy-format.md`](../archive/streaming-compatibility-specs/10-serialization-and-tidy-format.md).

## What this covers
Migrating the recorded output to a **tidy long** schema (one row per (frame, subject, segment/keypoint,
channel)) so downstream analysis is uniform across keypoints, positions, and rotations.

## To capture when authored
- The tidy-long column schema and how it maps from the frame channels.
- The relationship to the posthoc rebuild ([../02-pipeline/posthoc-rebuild.md](../02-pipeline/posthoc-rebuild.md)).

## Reconciliation notes
Align channel names with [../01-data-model/message-contract.md](../01-data-model/message-contract.md);
60/76 counts; `wxyz`.
