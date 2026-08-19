# On-Disk Serialization (tidy-long format)

**Describes (target):** the on-disk form of recorded reconstruction — tidy-long CSV/parquet vs. the
skellyforge parquet schema. **Not built yet** — this is the spec for the on-disk-serialization workstream.

## What this covers

Migrating the recorded output to a **tidy long** schema (one row per (frame, subject, segment/keypoint,
channel)) so downstream analysis is uniform across keypoints, positions, and rotations.

## To capture when authored

- The tidy-long column schema and how it maps from the frame channels.
- The relationship to the posthoc rebuild ([../02-pipeline/posthoc-rebuild.md](../02-pipeline/posthoc-rebuild.md)).
- Align channel names with [../01-data-model/message-contract.md](../01-data-model/message-contract.md);
  95/146 segment/landmark counts; `wxyz`.
