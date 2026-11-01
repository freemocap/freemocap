# Approved API cleanup checklist

Approved by the owner on 2026-10-31. Wording, numbering, and order are frozen.
Core worktree: `cleanup-api-terminology`. Follow the workspace human-owned Git
and independent-repository handoffs. See [implementation plan](recording-api-and-terminology-plan.md).

- [x] **1.** Map every current route to its implementation, callers, replacement route, compatibility requirements, and acceptance tests.
- [x] **2.** Implement shared recording identity, path resolution, and access coordination, verifying default directories and same-name recordings under different parents.
- [x] **3.** Migrate recording resources and playback routes with their UI callers, verifying metadata, calibration, timelines, video delivery, and revision handling.
- [x] **4.** Implement a common task interface for processing, exports, and synchronization, verifying HTTP/WebSocket status agreement, cancellation, and reconnect behavior.
- [x] **5.** Unify recording export options, artifact discovery, and export creation, verifying every existing format and automatic after-processing exports.
- [x] **6.** Rename export types, functions, UI settings, and configuration fields, verifying that supported historical settings still load.
- [x] **7.** Align processing, capture, import, realtime, and shutdown routes with their actual operations and callers, correcting response contracts and verifying existing workflows.
- [x] **8.** Isolate WebSocket client failures, verifying that malformed input or one disconnected client cannot shut down the backend or disrupt another client.
- [x] **9.** Remove remaining meaningless `scientific` terminology from active core code, UI, generated guides, and maintained documentation, validating affected contracts.
- [x] **10.** Rename SkellyForge provenance to `DataProvenance` and migrate its serialized contract, verifying supported old datasets and new round trips before the human handoff.
- [x] **11.** Integrate the reviewed SkellyForge changes into core after the handoff, verifying imports, metadata, and historical/new export compatibility.
- [x] **12.** Correct SkellyCam’s state-changing GET routes in its separate worktree, verifying standalone camera controls before the human handoff.
- [x] **13.** Migrate core’s camera-control callers after the SkellyCam handoff, verifying capture, recording stop, and pause behavior.
- [x] **14.** Reconcile Swagger categories, schemas, client URLs, and compatibility adapters, then validate the complete workflows and document any remaining limitations.
