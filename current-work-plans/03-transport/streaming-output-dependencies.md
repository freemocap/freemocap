# Streaming, avatar assets and viewer motion: revised agreement packet

2026-11-01, execution approved via the coordinator's verbatim user instruction:
"Okay, a couple of hard corrections there, but in general, I think what you're saying looks good. Let's nail this all down into checklist tasks and whatnot, and then let's get into it, ?"
Global/child wording below is frozen. Shared runtime 2.1–2.3 is locally verified,
including real-server SDK and browser controls. Canonical integration remains
coordinator-owned; live LSL and rendered/live VMC acceptance remain open.
LSL/VMC protocol preparation runs in separately owned files; root owns native mesh.
Canonical implementation has since advanced beyond this isolated source tree:
the SDK now has 65 HTTP operations, VMC has a no-body quick start, and the UI uses
an Outputs toolbar dropdown without timer polling. The default VMC profile is
now `vrm0_normalized`, with partial ancestor-valid branches. Read
`streaming-ecosystem-status-roadmap.md` for current evidence and proposed next
expansions. The approved global/child wording below remains unchanged; open live
and rendered acceptance tasks remain open. Publication is coordinator-owned.
This supersedes the dependency ordering in
`streaming-outputs-vmc-first.md`: LSL does not wait for VMC retargeting, and native
Skelly visualization is a separate lane. Existing JS/TS completion and evidence
remain unchanged. No package relocation is part of this implementation. Root owns
integration and the separate Skelly mesh investigation. Source acquisition time
and Forge's existing VRM-referenced rest/hierarchy definitions remain authoritative.

## Distinguish the deliverables

| Deliverable | What it does | What it depends on |
| --- | --- | --- |
| Shared server output runtime | Owns output IDs, configuration, start/status/stop, source access, errors and shutdown; UI controls it over HTTP | Existing pipeline/message boundary and app lifecycle |
| LSL output | Publishes selected numerical channels, metadata and timestamps through an LSL outlet | Shared runtime plus schema, clock and delivery-policy projection |
| VMC output | Sends named avatar poses through OSC/UDP to a receiver that has an avatar | Shared runtime plus a tested humanoid pose/rest-frame mapping |
| Native Skelly viewer | Displays a scaled, animated Skelly mesh using our own live and recorded data | Existing mesh asset/binding behavior, Forge poses, UI renderer; mesh owner's inspection determines exact work |
| Skelly VRM | Packages a suitable Skelly humanoid avatar for compatible external applications | Asset/rig preparation and VRM conformance; optional for initial VMC testing |
| Language SDKs and host integrations | Control FreeMoCap, consume full data and load recordings in external applications | Accepted HTTP/message/recording contracts, not completion of the avatar work |

VMC's ordinary motion messages contain root/bone transforms, not the mesh geometry.
Bone names follow the expected humanoid vocabulary; arbitrary anatomical segment
names alone do not make an arbitrary receiver rig work. Local frames, avatar rest
frames and original versus normalized VRM1 poses must match the chosen receiver
profile [@vmcProtocolSpecification]. Use an existing compatible avatar for initial
acceptance; producing our own Skelly VRM is not a prerequisite.

VRM is an avatar asset format: model, rig conventions, materials and avatar metadata
are distinct from the live motion sent to it [@vrmAvatarFeatures]. A Skelly VRM is
a plausible separate deliverable, but whether the existing Blender mesh can be
exported directly is not yet established. The mesh investigation owns that finding.
Our native viewer can use our existing WebSocket/recording path directly; neither
a VMC loopback nor VRM packaging is required merely to animate Skelly in Three.js.

The coordinator's mesh owner subsequently reported concrete source evidence:
Blender already has portable `assets/skelly_mesh.json.gz` schema 2;
`core_functions/parquet_scene.py` fits rigid asset groups once using anchors,
segment maps and roll bases, with segment-length scaling and a pelvis-width rule;
`parquet_import.py` drives independent bones from segment origins/world rotations.
This is an existing asset and fitting contract to reuse, not a need to reproduce
Blender's legacy per-frame constraints. This note records the owner's inspection;
browser parity remains unverified. Independent segment bones are not automatically
a conformant humanoid VRM hierarchy.

LSL provides its own transport library and outlet/inlet abstractions; FreeMoCap
should publish through that library rather than implement a custom TCP sender
[@lslIntroduction]. This bridge is independent of humanoid retargeting, but still
requires explicit channel identity/order/type/units, stream topology behavior,
source-clock conversion, missing-value semantics and measured delivery behavior.
LSL's sample clock is its local monotonic clock; arbitrary capture, wall-clock or
recording timestamps cannot simply be passed through as equivalent
[@lslTimeSynchronizationGuide]. For replay, retain original source timing while
explicitly mapping playback time to the outlet clock.

## Proposed global milestones and dependencies

Numbers are stable identifiers within this proposed revision, not a claim that
independent owners must execute the whole portfolio serially. Each owner's approved
child checklist remains linear. This proposal changes prior sequencing explicitly.

- [ ] **1.** Complete integration and verification of the existing JS/TS SDK and default-app changes under the coordinator's current landing plan.
- [x] **2.** Deliver the shared server output lifecycle, HTTP/SDK surface and UI controls with independent, nonblocking source consumption.
- [ ] **3.** Deliver the LSL numerical bridge with verified schema, timing, delivery behavior and independent receiver evidence.
- [ ] **4.** Deliver the VMC pose adapter with verified humanoid mapping and a receiving-avatar demonstration.
- [ ] **5.** Deliver scaled Skelly visualization in the native UI for live and recorded motion through the mesh owner's inspected implementation plan.
- [ ] **6.** Deliver Python and Rust SDKs with full supported controls, streaming and recording access through independent language-owner checklists.
- [ ] **7.** Deliver Blender, Unity, Unreal and Godot integrations using existing receivers where suitable and direct clients for remaining data, control and playback needs.
- [ ] **8.** Evaluate and, if selected, deliver a conformant Skelly VRM asset without blocking the initial VMC or native-viewer milestones.
- [ ] **9.** Verify versioned cross-target compatibility and complete reproducible installation, demonstration and packaging evidence.

Global 1 preserves completed SDK work; its integration status belongs to root.
Global 2 feeds globals 3 and 4; the two protocol projections can be developed in
parallel against that agreed interface. LSL does not depend on VMC or global 5.
Global 5 runs independently using existing data, and shares verified pose/binding
facts with globals 4 and 8. It does not automatically supply a VRM humanoid rig.
Global 6 can proceed independently. Global 7 can start VMC receiver demonstrations
after global 4 while fuller SDK/recording integrations proceed separately.
Global 8 is a decision milestone: acceptance may explicitly defer the asset;
optional discussion here does not authorize creating it now.

## Current planning expansions

Only the shared runtime and protocol bridges are expanded here. The coordinator's
mesh agent owns global 5's source inspection and child proposal; no duplicate mesh
design or speculative child tree is introduced.

### Global 2: shared output runtime

- [x] **2.1.** Define the output-instance, source-selection, status and failure contracts as a delta to the existing server API and channel contracts.
- [x] **2.2.** Implement and test app-owned output lifecycle and independent source consumption with bounded resources, concurrent outputs and complete cleanup.
- [x] **2.3.** Expose output discovery, start, status and stop through HTTP, SDK bindings and UI controls, and verify observed-state behavior end to end.

Retain start-idle, ephemeral server configuration, output IDs and scoped failures
from the recovered strategy. Reuse `FreemocapApplication`, current pipeline result
interfaces and `core/streaming/message_composer.py`; verify cursor/event ownership
so output consumers neither depend on browser connections nor steal their state.
Suggested location remains internal Core `core/streaming/outputs/`, with existing
API/UI ownership. Do not require a new top-level output repository.

Shared lifecycle does not mean identical buffering: a latest-pose policy can suit
VMC, but applying it silently to a research time series would hide dropped samples.
For LSL, inspect whether the present latest-result source meets the declared
delivery profile; if not, use an appropriate bounded source subscription and report
loss/overflow explicitly. A slow output must not block acquisition or inference.

### Global 3: LSL bridge

- [x] **3.1.** Define and independently test LSL channel metadata, stream identity/topology, source-to-LSL clock mapping and missing/drop semantics using existing reference data.
- [x] **3.2.** Implement the LSL outlet projection through the shared output runtime and verify start, stop, schema changes and transport failure behavior.
- [ ] **3.3.** Validate reference replay and coordinated live capture with an independent LSL inlet or recorder, comparing values, timestamps, sample counts and cleanup.

Use the LSL library for transport/discovery/synchronization. Test the chosen
rate/chunking policy rather than assuming a nominal rate or arrival timestamp
represents the capture clock. Library installation/distribution and supported
platforms are explicit implementation work, not already completed capability.

### Global 4: VMC bridge

- [x] **4.1.** Select a receiver/avatar profile and verify named humanoid mapping, rest frames, local poses, units and coordinate conversion with independent known-pose fixtures.
- [x] **4.2.** Implement VMC projection and OSC/UDP emission through the shared output runtime with packetization, missing-data and concurrent-destination tests.
- [ ] **4.3.** Demonstrate reference replay and coordinated live motion on the selected receiver's existing avatar, and record numeric and visible acceptance evidence.

Reuse Forge's existing coordinate and pose mathematics. Keep any reusable geometry
extension there, while Core projects its composed data into the protocol. Do not
duplicate math, fabricate unavailable expressions, or describe a model as supported
solely because names match. Root/body/finger/expression capabilities must be explicit.
Do not equate successful UDP sends with receiver connectivity or correct animation.
Custom Skelly VRM creation is not part of this child list.

## Open engineering work and approval boundary

No new product interview is needed. LSL clock/delivery mapping and reference
validation are implemented; fresh live numeric acceptance remains open. Canonical
VMC now includes a normalized VRM0 default and an opt-in original-reference profile;
rendered receiver acceptance, placement and partial-body behavior remain open.
Native mesh work remains separately owned. Do not repeat completed contract
discovery or treat source implementation as receiver acceptance.

Reuse existing golden/reference fixtures and add protocol-specific independent
assertions. Actual live capture requires a coordinated hardware slot. No receiver,
outlet, avatar exporter or mesh prototype was launched for this planning revision.
The user subsequently approved execution through the coordinator. Root consolidates
integration and assigns active owners; renderer/asset files remain outside W6 ownership.
