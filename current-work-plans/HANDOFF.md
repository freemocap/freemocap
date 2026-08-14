# Handoff — 2026-08-14 (realtime loop at the F5 gate)

**For a fresh agent (or the same one after compaction).** Read [`ontology.md`](ontology.md) first, then this
file, then [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md)'s progress log (history only — the layer docs
are the live plans). The archive/ tree is history.

## Orientation in one page

FreeMoCap turns multi-camera frames into a streamed, canonical human. The settled ontology
([ontology.md](ontology.md)): **keypoint** (measured 3D point, tracker-named — skellytracker) →
**mapping** (the one seam: hydrates landmarks from keypoints — the four YAMLs) → **landmark** (a
segment-local named point; two faces: static rest definition + per-frame world hydration — skellyforge) →
**segment** (an oriented volume; graded: 2 landmarks = simple, twist carried by the damped roll; 3+ =
full 6-DOF via the MDS-template + Procrustes fit) → **skeleton** (rooted tree; joint angles derived,
`q_local = conj(q_parent)·q_child`). The future constraint/solve layer (typed linkages, chains/IK,
twist-backfill) is **seams only** — it adds constraints later, NOT stability now. The now-DoD: a
**VMC-compatible realtime segment stream** to the frontend.

**The stabilization stack (answered + settled 2026-08-14 — do not re-litigate):** Euro filter (keypoints)
→ tree/fit rigidification (enforced lengths/shapes — the 2-landmark tree pass IS the old
skeleton-rigidifier; the 3+ landmark per-group fits are strictly stronger) → critically-damped
orientation solve (D3/D4). The old rigidifier's stabilizing effect is fully preserved. The future
linkage layer is not needed for it.

## Where the work stands (all green)

| Repo | State (the user committed everything on 2026-08-14) | Suite |
|---|---|---|
| skellyforge | the landmark sweep (`rigid_points`→`landmarks`, `origin_keypoint`→`origin_landmark`, `target_keypoint`→`target_landmark`, `required_keypoints()`→`required_landmarks()`, `ReferenceGeometry.keypoints`→`landmarks`), the face-provenance reword (canon owned on this side), `test_face_mapping_consistency.py` (pins the cross-repo ratio agreement at TEST time — the runtime is tracker-free) | **148 green** |
| skellytracker | the mapping language sweep (`TrackerMapping.keypoint_names`→`landmark_names`; `known_tracker_keypoints` stays; the four YAML headers say "keys are landmark names; values hydrate them") | **234 green** |
| freemocap | the docs reorg + the whole F0–F4 body of work | **108 green** (the green subset); TS harnesses: decoder 5, renderer 11; `tsc` clean |

**First action on pickup: verify the REMOTE tips.** freemocap's env installs the skellies **from git** —
committed-locally is not enough; the sweep commits must be on the `development-streaming` remotes and
freemocap re-locked (`uv lock --upgrade-package skellyforge skellytracker && uv sync`) before any
freemocap code touches the new names. `git ls-remote origin development-streaming` in each skelly and
compare against the local HEADs.

## What exists end-to-end (the F0–F4 work, all reviewed)

- **Skellyforge**: the 60-segment VRM-1.0 model (`SegmentDefinition(landmarks, origin_landmark, axes:
  AxisDefinition(axis: Literal["x","y","z"], kind: EXACT|APPROXIMATE, target_landmark), rest_rotation,
  rest_roll, length_ratio)`), name-driven two-pass frame builder (all EXACTs hard on their named vectors
  first, APPROXIMATEs Gram-Schmidt'd — the approximate-before-exact ordering bug is fixed), VRM local
  conventions (+Y toward child; +Z gaze for eyes/jaw; rest frames derived from the T-pose geometry),
  reference geometry (identity == T-pose), the keypoint-declared solver (two-tier twist: own-geometry
  resolve or damped minimal roll; D3/D4 damping), `rigid_point_set.py` (MDS template chirality-stabilized
  + rotation-only Procrustes, bs-repo-derived, pyceres deliberately NOT ported), the one length
  estimator (windowed/unbounded), `tracker_contract.py` (the ONE sanctioned skellyforge→skellytracker
  import: the load-time completeness contract).
- **Skellytracker**: the four mapping YAMLs (all 76 landmarks produced per tracker; MediaPipe mouth
  corners real, RTMPose derived via `anatomical_offset`), `TrackerMapping` (four production forms +
  `known_tracker_keypoints` load-time raise), the light `mapping_paths` registry.
- **Freemocap**: the wrapper's graded dispatch (2-landmark span path via `TreeRigidifier`; 3+ per-group
  fits — head 7 / hips 4 / feet 3 / toes 3, anchored at the tree-corrected origin, 30-frame
  chirality-stable template rebuilds), the six-group schema (KEYPOINTS_3D, SEGMENT_ORIGINS,
  ROTATIONS_LOCAL/WORLD, DERIVED_POINTS, OVERLAY_2D; `segment_lengths` shipped with
  defaults-then-material-change re-sends; frozen), the sample encoder (golden fixtures for cross-language
  parity), the WS send-path decomposition (SendSerializer one-writer / BackpressureController /
  FrameRelay / thin supervisor), D36 legacy deletion, the de Leva CoM, the TS transport + decoder +
  rolling windows + the rigid-body renderer (schema-driven lengths, D5/D6/D14/D15 fixed).
- The calibration `groundplane_aligned` one-liner is fixed; the pyceres calibration pipeline is DEAD
  (leave it); the D35 convention gap (camera-0-pinned calibration delivers optical-frame data) is
  documented and DEFERRED to the calibration round.

## The queue (in order)

1. **[USER] Push skellyforge + skellytracker to the remotes** (committed locally already), then
   freemocap `uv lock --upgrade-package skellyforge skellytracker && uv sync`. Verify the installed
   shapes: `uv run python -c "from skellyforge.skellymodels.standard_human.segment_definition import
   SegmentDefinition; assert 'landmarks' in SegmentDefinition.__dataclass_fields__"` and
   `TrackerMapping` has `landmark_names`.
2. **Sweep 3 — freemocap + TS + docs** (the landmark vocabulary in the wrapper/CoM/schema builder;
   **the dual channels**: KEYPOINTS_3D repurposes to the tracker-named measured keypoints — the schema
   builder gains a `tracker_keypoint_names` param from the mapping's tracker side; a NEW `LANDMARKS_3D`
   channel carries the 76 — through the encoder, the aggregator message (adds the full tracker-named
   keypoint set), goldens, and the TS mirror/decoder; plus the deferred fixes: **A2** (FrameRelay stop
   signal), **B1** (ack window counts actual in-flight sends, not frame-number deltas), **B2** (schema
   rebuild only on the material-change fire — predicate first), **S2** (remove the per-frame
   `StreamingSegmentLengthMonitor` + the old `segment_lengths.py` live path from the aggregator), the
   default-height unification (1700 vs 1750 → one constant), the DERIVED_POINTS positional-index fix,
   the TS stale comments; docs: the glossary boundary line ("the mapping's output is always a landmark —
   the production form is the mechanism"), the segment-model scaffold's "no landmark layer" line, the
   dropped-observed-DOF decision record in the ontology seams, count drift).
3. **[USER] Push freemocap.**
4. **F5 — the gate**: backend full-loop test (aggregator → sample → bytes → decode → identical
   rotations; a mock-camera realtime run producing non-NaN ROTATIONS_WORLD) + the frontend integration
   test (connect → schema → samples → renderer instances placed). Then **the user's manual full-loop
   run** — the checklist: T-pose at capture start, arm bend rotates the humerus mesh without pop,
   hidden-hand degradation, no schema drift.
5. **F5+1**: the thin VMC adapter (VRM 1.0→0.x name map; the local frames are already VMC-ready). Then
   the posthoc rebuild opens ([`02-pipeline/posthoc-rebuild.md`](02-pipeline/posthoc-rebuild.md)).

## Locked decisions (do not re-litigate)

- Landmark is REVIVED with the precise two-faced meaning; "canonical" (mapping sense) stays retired;
  `from/to_keypoint`, `long_axis`, `twist_keypoint` are retired. Code/comments describe the system AS IT
  IS — never by contrast with removed designs.
- All axis targets inside the segment's own landmarks — no external references ever (the upper arm's
  wrist case was the lesson). First-axis-is-EXACT positional rules are dead; the machinery is
  name-driven.
- VRM local conventions (+Y toward child, +Z gaze) — the VMC adapter is a pure name map later.
- The observed/unobserved-DOF flag is **dropped** (complexity > value; the damped roll fills unobserved
  twist; the graded landmark count remains the seam). Record this in the ontology if not yet recorded.
- The rest-pose/model side never imports skellytracker at runtime — the sanctioned import is
  `tracker_contract.py` ONLY. The face/mouth cross-repo ratios are pinned by a TEST, not shared.
- The stabilization stack needs no new work (see the orientation section).
- **Open**: `data_models/observation.py`'s silent try/except shim import (the known Phase-E item — the
  user hasn't chosen fix-now vs E4).
- **Working rules** (unchanged): never touch git (the user owns it — report stopping points); plan==code
  (docs edited in the same pass); fail loudly; no duplicated information; no backwards compat; cross-repo
  work ends at commit rounds; ask before unilateral design decisions.

## Env

- WebFetch broken (DeepSeek routing) — use curl + WebSearch.
- Suites: skellyforge `uv run --with pytest pytest skellyforge/tests/ -q -o addopts=""` (148);
  skellytracker `uv run pytest skellytracker/tests -m "not video" -q` (234); freemocap
  `uv run --group dev pytest freemocap/tests/rigid_body/ freemocap/tests/test_standard_stream_contract.py
  freemocap/tests/test_stream_schema_builder.py freemocap/tests/test_center_of_mass.py
  freemocap/tests/test_stream_sample_encoder.py freemocap/tests/test_backpressure_controller.py
  freemocap/tests/test_send_serializer.py freemocap/tests/test_frame_relay.py -q` (108); TS: the
  house harnesses (esbuild+node — there is NO Vitest despite what older docs say) + `npx tsc --noEmit`.
- The golden fixtures regenerate via `uv run python -m freemocap.tests.streaming_fixtures.regenerate_golden`
  and are re-copied into `freemocap-ui/src/services/server/transport/__fixtures__/` (sha-identical —
  they are the cross-language parity anchors; regeneration IS a wire change).
