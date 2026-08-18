# Testing Strategy

How the two efforts are verified, and the two runtime invariants the tests defend.

## Runtime invariants

- **Fail loud at load.** Segment / model / reference-geometry / estimator validators raise on a bad
  declaration (a missing rigid edge, a mapping that references a keypoint the tracker never produces).
  Nothing silently disables a feature.
- **Occlusion is data.** A keypoint missing *this frame* is not an error — the segment is skipped this
  frame. A *declared* coincidence is impossible (the load-time validators forbid it).

## Test layers

| Layer | What it pins | Where |
|-------|--------------|-------|
| **Unit — model** | Segment/axis validation, composition, reference geometry (right-handed, mirroring, scales linearly), `identity == T-pose` (world + local). | skellyforge `tests/` |
| **Unit — kinematics** | Quaternion algebra, Kabsch/Umeyama, the orientation solver's two tiers, the damped filter, the rigid-fit (MDS + Procrustes). | skellyforge `tests/` |
| **Completeness contract** | Every tracker mapping produces the full landmark set; a gap raises at load. | skellyforge `tracker_contract.py` + tests |
| **YAML definition loader** | `HumanSkeleton.from_yaml` composes parts, resolves references to objects, mirrors the right side, and derives lengths; a bad reference fails at load. | skellyforge `tests/test_lower_body_skeleton.py` |
| **Wire contract** | message **golden bytes**; Python encoder ↔ TS decoder parity. | freemocap `tests/` + freemocap-ui harness |
| **Backend integration** | frame message build, WebSocket send-path (serializer / relay / backpressure). | freemocap `tests/` |
| **Full loop (F5 — the gate)** | Cameras → tracker → map → estimate → solve → encode → transport → decode → render, end to end. Landed: the backend loop test (`test_full_loop.py`) + the TS integration harness. **The manual full-loop run is the user's gate** (T-pose at start, arm bend without pop, hidden-hand degradation, no schema drift). Gates the posthoc rebuild. | backend `test_full_loop.py` (2) + TS integration harness (3) |

## Identity-at-T-pose

The load-bearing model test: feed the reference geometry (± a realistic off-chain `nose`) back as live
input; every solved segment must return identity. The head specifically is exercised with an anterior
`nose` so a corrupted reference forward-axis can't hide in the damped tier (regression added 2026-08-14).

## Running

`pytest` is in neither default env. skellyforge:
`uv run --with pytest pytest skellyforge/tests/ -q -o addopts=""`. freemocap:
`uv run --group dev pytest freemocap/tests/…`. freemocap-ui: `npm test`.

## Sources
Fresh from the suites above.
