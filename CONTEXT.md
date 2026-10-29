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

**Clock domain**:
The time basis in which a source's timestamps have meaning, including its origin
and epoch. Relating distinct clock domains requires an explicit synchronization relation.
_Avoid_: Assuming equal frame numbers or nominal frequencies establish synchronization.

**Sample timeline**:
An identified ordered sequence of sample IDs and timestamps in one recording clock
domain. Sources sharing a clock can have different sample timelines.
_Avoid_: Using one global frame index for every source in a recording.

**Recording dataset**:
An identified collection of scientific measurements with their axes, timelines,
missingness, definitions and provenance. A recording dataset can contain multiple independent sample timelines.
_Avoid_: Treating a single synchronized array as the whole recording.

## Naming guidance

Use meaningful two-word names for domain concepts, proposed types and public
interfaces, in both explanations and new code. Name what the thing contains or
does: data tensor, time series, channel layout, sample timeline,
entry presence, value validity, confidence scores, solver status. Do not introduce
vague standalone names such as block, snapshot, data, context or manager.
Use established single-word terms only when genuinely unambiguous and explain
non-obvious exceptions. Existing code identifiers and external API names remain
accurate when quoted; this rule does not authorize incidental compatibility breaks.
Use the same term in prose, type names and serialization descriptions.

**Data tensor**:
A numeric array with explicit ordered axis definitions; each dimension derives
from its identifiers. Neither time nor empirical origin is implicit. Live and
post-hoc processing use the same authored entity and declared component order.
_Avoid_: Block as a name for scientific data, or fixed coordinate counts in generic storage.

**Time series**:
A data tensor whose designated sample axis binds to sample identifiers and
timestamps. It may carry measurements, estimates, predictions or generated data;
scientific provenance preserves those distinctions. Current timestamp production
is unchanged by the initial layout implementation.
_Avoid_: Measurement series as the generic container name.

**Companion tensors**:
Separate typed arrays describing entry presence, value validity, confidence,
measurement support or solver status. Declare their axes and semantics explicitly.
Component metadata matches measurement shape; entity metadata omits the component
axis and can broadcast without allocating duplicate values.
_Avoid_: One ambiguous quality mask combining unrelated scientific meanings.
