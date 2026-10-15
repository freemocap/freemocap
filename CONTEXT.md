# Recording processing language

Domain terms settled during the posthoc dataflow work. Detailed contracts remain
in the recording and pipeline design documents.

## Saved-data retention

Processing stages owns two choices: the source run supplying saved inputs and
whether to overwrite that run or keep it and create a new run. Changing controls
does not modify saved results. On successful checkpoint publication, overwrite
replaces the computed products and removes affected downstream products and
completion records from that Parquet run. Other runs and sensor groups remain.
Keep creates a separate Parquet run, carrying forward reusable prerequisites with
their provenance; the source run remains unchanged. One destination ID serves the
whole attempt. Reserving its output folder prevents reuse after a failed attempt.

Exported files remain until regenerated outputs replace their matching names.
Run 0 uses ordinary filenames; later runs use run-ID suffixes and `run-<id>`
folders within the relevant output location. Overwriting Run 2 updates Run 2's
files. It does not create Run 3. Automatic cleanup removes only temporary files
and publication journals. Cancelled or failed writes leave the previous checkpoint
intact; earlier successfully saved checkpoints can remain after later failure.
The opt-in stage-range matrix targets test data; do not repeat it on sample data
for this work.

## Language

**Motion-capture frame**:
One recording position across the declared camera group, identified by its frame
index and associated timeline. Three camera images at that position count as one
motion-capture frame.
_Avoid_: Frame count without identifying whether it counts camera images or group positions.

**Camera annotation**:
A video representation of one camera's images with the requested tracking and
board observations drawn on them. It is an independent output, not a prerequisite
for scientific reconstruction.
_Avoid_: Tracking when referring only to drawing or video encoding.

**Scientific completion**:
Successful completion and validation of all requested scientific products for the
declared inputs. Failure of a required camera prevents complete scientific output.
_Avoid_: Treating some available 3D points as a complete recording.

**Recording-run completion**:
The terminal outcome of every requested product, including scientific products,
annotations and exports. A finished run can contain explicitly reported failures.
_Avoid_: Calling a run successful while requested products remain unfinished or failed.

**Annotation job**:
The requested annotated video for one camera in one recording execution, with its
own completion or failure outcome.
_Avoid_: Using camera identity alone to identify work across different recording runs.

**Saved stage**:
A complete, validated scientific result that can supply inputs to a later processing
attempt. It is a durable restart boundary, not a requirement to pause downstream computation.
_Avoid_: Using stage to mean a global scheduling barrier.

**Stage restart**:
A new processing attempt that reuses explicitly selected saved scientific inputs
and recomputes the requested dependent results.
_Avoid_: Resume when implying continuation of an interrupted worker's in-memory state.

**Retained run**:
A saved result slot that can be replaced or preserved while a new run is created.
Its run ID identifies the slot; its revision identifies the particular saved content.
_Avoid_: Treating a run ID as immutable content identity.
