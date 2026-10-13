# WebSocket static-definition reuse audit — 2026-10-13

Scope: read the current backend composition/relay and frontend transport paths.
No transport protocol or renderer changes are part of the reconstruction batching.

- `websocket_server.py::_ensure_composition` compares live configuration and
  tracked-skeleton identity before building a context. `_skeletons_for` caches
  the model set. `message_composer.py::compose_messages` constructs definitions
  on model changes, while `compose_frame_message` reuses those definitions.
- `FrameRelay.set_composition` increments model_sequence on replacement. Frames
  remain self-contained; a client does not need an earlier definition message.
- `TransportService.updateStaticModel` compares received model, camera and
  convention contents using `snapshotEqual`, retaining existing objects and
  suppressing redundant static notifications when contents match. Changed
  contents win even if model_sequence is unchanged. This meets the requirement
  that the client faithfully represents the server's actual messages.
- Remaining per-frame work includes CBOR serialization/deserialization, recursive
  byte ownership normalization, schema validation, content comparisons and dynamic
  channel packing. Reuse does not mean these costs are zero. No measured transport
  bottleneck has been established by this reconstruction experiment.
- Do not replace content comparison with revision-only gating: it would break
  the existing same-revision changed-content regression contract. A future
  content fingerprint/prepared decoding optimization needs its own measurements
  and must preserve that contract and reconnect behavior.

Verification targets: `test_stream_composition_cost.py`, `test_frame_relay.py`,
`test_camera_only_websocket.py`, and frontend `snapshot-reconciliation.test.ts`.
Results will be recorded after the full-pipeline timing runs finish, so these
checks do not compete with the measured processing work.

Validation completed: 13 backend tests passed (composition reuse/invalidation,
relay messages and camera-only connection cleanup). The existing frontend
snapshot-reconciliation test also passed: changed contents update the client even
at an unchanged revision; equivalent contents retain the previous object; empty
contents clear the previous model. No source changes were needed for this audit.
