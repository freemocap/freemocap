# Calibration exports and model output cleanup

Typed data flow graph V1 reads the selected calibration without copying or
modifying it. Previously the application created an identical hash/UUID-named
file before every run. The graph only recorded a proposed calibration update in
the recording metadata; processing did not actually apply that update to the copy.

When a completed scientific result changes camera geometry, the graph now saves
that derived calibration under `exports/calibration_copies/`. The filename is
`<original-stem>__aligned__<UTC-timestamp>__<12-character-content-hash>.toml`.
No file or directory is created if there are no transforms or the cameras remain
exactly unchanged. Identical validated exports are reused on later runs. Comparison
includes the full calibration and transformation history; the hash alone is not
accepted as evidence of equality. No numerical tolerance discards small changes.
Publication validates a temporary TOML before replacing its final destination.

The original calibration remains untouched. The existing explicit
"Apply processed transforms to calibration file" action still targets the original
source revision and requires that revision to remain unchanged. It is a separate,
user-requested edit, not an automatic processing side effect.

This does not change the calibration solver's separate recording, calibration
library, and last-successful saves. Those support recording provenance, calibration
selection, and the most-recent calibration shortcut respectively.

Existing recording folders are not migrated automatically: older recording metadata
may reference their calibration copies. New runs follow the new export policy.

## Next independent repository stage

`freemocap_blender_addon/export_api.py` currently puts optional FBX/BVH files into
`<blend-parent>/3d_models`. Its Parquet configuration accepts only `formats` in the
model-export section. Move the model output default to the recording's
`exports/3d_models` in the add-on's export API, covering both Parquet and legacy
routes. Keep the `.blend` destination contract unchanged. Test custom `.blend`
destinations as well as defaults. After that repository's commit/push and core's
dependency refresh, update core's Blender integration assertion and run the real
export integration test. Do not work around the API by moving generated files
after export or duplicating its internal scene/export implementation in core.

Core's configured add-on source branch is `development-streaming`; verify the
add-on checkout before editing. This stage awaits the workspace's human-owned
commit/push handoff for the current core changes.
