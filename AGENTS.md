# Core repository guidance

Follow the containing workspace's ownership and review rules. Leave changes
unstaged and uncommitted for human review.

Tracker owns detector recipes, crop rules, keypoint assembly, schemas/connections,
and preset-specific mapping selection. Import its public preset/profile interfaces;
do not define equivalent detector trees or keypoint-selection rules in Core.
Core translates application settings and coordinates cameras, Tracker, Forge,
recording and transport. Distinguish detector keypoints, Tracker mapping rules,
and Forge anatomical landmarks when naming code and describing responsibilities.

## Recover the current task

At milestones, preserve the task objective, user corrections, architectural
decisions and reasons, existing interfaces, exact checkout, tests actually run,
and next action in the task's checkpoint. Include a short reading list with paths
and the question each source answers. Keep the approved plan and approval state.

After compaction or handoff, reread that checkpoint and the relevant ownership
guidance before editing. Select only the sources needed for the next action:

- Data meaning: [ontology](current-work-plans/01-data-model/ontology.md).
- Geometry boundaries: [conventions](current-work-plans/00-foundation/conventions.md).
- Dense arrays and identity ordering: [tensor contract](current-work-plans/01-data-model/tensor-contract.md).
- Tracking integration: [composition integration](TRACKER_COMPOSITION_INTEGRATION.md).
- Recording/provenance: [recording contract](RECORDING_CONTRACT.md).
- Strategy: the checkpoint's named plan, located through the
  [plan index](current-work-plans/README.md); distinguish proposals from implementation.

Inspect the relevant diff and existing public interfaces before adding behavior.
Core owns a change only when it inherently coordinates multiple subrepositories.
Missing summary context is a reason to search, not to recreate component logic.
Continue authorized work once purpose, ownership and validation are clear; ask
only when consequential intent remains unresolved after targeted inspection.
Preserve unrelated work and leave all Git mutations to the human.

## Self-describing transport is an intentional invariant

Every message must remain independently interpretable. Repeated metadata and its
bandwidth cost are accepted to prevent server/client state mismatch. Preserve this
strategy and the existing mechanisms that handle repetition efficiently; do not
propose state-dependent or delta-only messages during unrelated feature work.

Before changing or assessing transport/visualization cost, read
`current-work-plans/03-transport/message-protocol.md` for the rationale, then trace:

- `freemocap/core/streaming/message_composer.py` and `message_model.py`: static
  composition and self-contained encoding.
- `freemocap/api/websocket/frame_relay.py`: actual frame delivery.
- `freemocap-ui/src/services/server/transport/cbor-codec.ts` and
  `TransportService.ts` and `snapshot-equality.ts`: connection-owned validation,
  reconciliation, and identity reuse (tested in `receive-reuse.test.ts` and
  `snapshot-reconciliation.test.ts`).
- `freemocap-ui/src/components/viewport3d/ThreeJsCanvas.tsx` and
  `viewport-frame-transfer.ts`: change-driven static subscriptions and reusable
  frame-sized numerical transfers.

Check the associated tests and current strategy before suggesting alternatives.
Distinguish wire repetition from repeated construction, validation, preparation,
or worker transfer. Correct agent-authored constraints that contradict these
established decisions without asking the owner to approve the architecture again.


When external research, documentation, tutorials or source code informs a change,
follow [CITATIONS.md](CITATIONS.md): register the source in root `references.bib`,
cite its stable key beside the supported claim, and record review scope honestly.
Run the bibliography validator and its tests before handoff. Preserve useful
background references even when they have no current inline citation.
