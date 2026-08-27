# Testing Strategy

How the two efforts are verified, and the runtime invariants the tests defend.

## Runtime invariants

- **Fail loud at load.** Skeleton / rest-pose / component validators raise on a bad declaration (an
  unknown alias, a `connect_at` the parent does not own, a mapping that references a keypoint the
  tracker never produces). Nothing silently disables a feature.
- **Occlusion is data.** A landmark missing *this frame* is not an error —
  `hydrate_skeleton(require_all=False)` skips the segments that cannot solve and the loop publishes
  what exists (NaN rows on named channels). A *declared* impossibility (duplicate names, reflected
  bases) still fails at load.
- **Boundaries hold.** skellyforge never imports skellytracker/freemocap (`test_no_cross_import.py`);
  every key of skellytracker's mapping YAMLs is a real skellyforge landmark
  (`test_tracker_mapping_boundary.py`) — the two sides cannot drift apart silently.

## Test layers

| Layer | What it pins | Where |
|-------|--------------|-------|
| **Unit — math kernel** | Quaternion algebra + round trips, slerp/batching, orthonormal bases (incl. left-handed), Transform round trips, PointRingBuffer windows, tolerances, shortest-arc edge cases, Umeyama similarity recovery/reflection/collinear rejection. | skellyforge `tests/` |
| **YAML loader + model** | `$include` composition/equivalence, lowercasing, sided expansion + x-mirroring, alias resolution, origin-at-zero, whole-skeleton loads (**61 segments / 124 landmarks**, fully-specified set), every fully-specified segment solves to its own authoring frame. | skellyforge `tests/test_skeleton_yaml_loader.py` et al. |
| **Pose** | Rest-pose geometry (trunk up, arms out, legs down, both feet on one flat ground plane), hydration rigid/direction/partial paths, roll continuity + reset, length estimation, synthetic round trip. | skellyforge `tests/` |
| **Biomechanics** | de Leva fractions sum to 1, segment mapping totality (61→16 sided names), whole-body CoM midline in T-pose, inertia SPD, CoP/XCoM/CMP formulas, derived kinematics timestamp validation. | skellyforge `tests/` |
| **Wire contract** | ChannelBlock packing + CBOR round trips; golden-message fixture (regenerator in `streaming_fixtures/`). | freemocap `tests/test_message_model.py` + freemocap-ui Zod contract |
| **Backend integration** | Full compose→encode→decode round trip from synthetic rtmpose observations through the REAL mapping + hydrate + resolve path; arm abduction ≈90° with chest still; FrameRelay over a FakeWebSocket. | freemocap `tests/test_full_loop.py`, `tests/test_frame_relay.py` |
| **Pipeline e2e** | MockCameraGroup lockstep: charuco_only + full modes; CoM assertions when skeleton enabled. The manual F5 run remains the user's gate (T-pose identity at start, arm bend without pop, hidden-hand degradation, overlay match). | freemocap `tests/pipelines/` |

## The model gate (what replaced "identity-at-T-pose")

Feed each fully-specified segment's own rest positions back as live input — it must solve to its own
authoring frame (`test_every_fully_specified_segment_solves_to_its_own_authoring_frame`). This keeps
Gram-Schmidt reference geometry and FK local positions one answer to "which way does this segment face".
Direction-only segments are pinned by `test_synthetic_round_trip.py` instead: synthesize poses from the
rest pose → hydrate → recover exactly (plus noise robustness and `solved_by` reporting).

## Running

`pytest` is in neither default env. skellyforge:
`uv run --with pytest pytest skellyforge/tests/ -q -o addopts=""`. freemocap:
`uv run --group dev pytest freemocap/tests/…`. freemocap-ui: `npm test`.

## Sources

Fresh from the suites above.
