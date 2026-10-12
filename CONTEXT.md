# Recording processing language

Domain terms settled during the posthoc dataflow work. Detailed contracts remain
in the recording and pipeline design documents.

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
