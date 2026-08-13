# 10 — Whole-Project Alignment: keypoint → segment reference geometry

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development` (recommended)
> or `superpowers:executing-plans` to implement this task-by-task. Steps use checkbox (`- [ ]`) syntax.
>
> **Status: plan for agreement — no code until agreed.**
>
> **This supersedes the D7/D8 "finish or revert" question and the piecemeal task ordering.** The paused
> D7/D8 work was built on the retired tracker→canonical-landmark framing, so it cannot be *finished* — it
> can only be *disposed of*: the keypoint-level half survives as the new framing's own artifact, the
> graph-level half reverts. That realization is the step back this doc records, and the ordered path below
> is the re-derived whole-project work list it produced.

**Goal:** Align the whole project — skellyforge, skellytracker, freemocap, and the docs — on one segment
model whose reference geometry is defined **directly from tracker keypoints**, with no canonical-keypoint
or landmark layer anywhere in the path.

**Architecture:** One composed 55-segment VRM 1.0 model in skellyforge (Tasks 1–5 of
[`09-segment-model.md`](09-segment-model.md)); skellytracker's mappings guarantee that every keypoint the
model declares is actually produced (Task 6, renamed files); the solver reads declared keypoints (Task 7);
one length estimator (Task 8); the old models and bridges are deleted, not ported (Task 9); the posthoc
model layer — the one piece no plan owned — gets rebuilt onto the composed model (Phase E); the stream
side and the docs follow once the model is in freemocap's env.

**Tech stack:** unchanged — Python 3.11+, numpy, pydantic (model), dataclasses (hot path), pytest.

---

## 1. Why the D7/D8 pause is answered by supersession, not by a fix

D7/D8 (bilateral sternoclavicular) paused mid-flight because [`08`](08-skellyforge-alignment.md)'s survey
found the `canonical_body.yaml` graph the work was editing is itself the old model. The step back: **the
work's own mechanism was the old framing.** It added `sternoclavicular` to the "canonical landmark set"
and rerooted the three graph encodings (`segment_connections`, `bone_length_ratios`,
`joint_hierarchy`) — the exact structures the segment model replaces (deleted in SF-SM Task 9), in the
exact vocabulary ("canonical landmarks") that is now retired.

Under the keypoint → segment reference geometry framing, the same goal is achieved by **one line in the
Task 3 table** — `shoulder.origin_keypoint = sternoclavicular` — plus the already-written
`anatomical_offset` entries that produce `left_/right_sternoclavicular` as **derived keypoints** in both
tracker mappings. The keypoint-level work was always right; the graph-level work was always doomed.

So the disposition is per-file, not per-defect:

| Repo | File (uncommitted) | Disposition | Why |
|---|---|---|---|
| skellytracker | `rtmpose_body_to_standard_human_mapping.yaml` (renamed 2026-08-13) | **KEEP** | Bilateral SC via `anatomical_offset` is exactly the new framing's derived-keypoint mechanism; folds into Phase B untouched |
| skellytracker | `mediapipe_body_to_standard_human_mapping.yaml` (renamed 2026-08-13) | **KEEP** | same |
| skellytracker | `core/io/tracker_mapping.py` (D39: unknown offset axis now raises) | **KEEP** | fail-loud is the house rule; new-framing-neutral |
| skellyforge | `skellymodels/tracker_info/canonical_body.yaml` | **REVERT** (user git action — see §2) | The SC-landmark additions + `segment_connections` reroot + symbolic `bone_length_ratios` are edits to a graph stack that dies in Phase D. The file is currently **internally inconsistent** (`joint_hierarchy` still routes `neck_center → left_shoulder`); the committed HEAD state is at least consistent, and nothing durable is lost — SC survives in the mappings, and Phase D re-derives the keypoint list from the model |
| freemocap | docs + 4 test-import fixes (this session) | **KEEP** | working-tree; user commits at convenience |

- [x] **Step 1 (user):** revert `canonical_body.yaml` (done 2026-08-12/13) — `git restore skellyforge/skellymodels/tracker_info/canonical_body.yaml` in the skellyforge repo (the working rule: the user owns git; never touch it from the agent side).

---

## 2. The ordered path

Phases are ordered; each ends at a verification point or a commit round. `(user)` marks git/commit steps.

### Phase A — the segment model (SF-SM Tasks 1–5) · skellyforge only

Foundation; no cross-repo friction. Detail in [`09`](09-segment-model.md).

1. [x] **Task 1** — `SegmentDefinition` (fully specified: tests + implementation written out in the doc).
2. [x] **Task 2** — part composition (`SegmentPart`, `compose_parts`; fully specified).
3. [x] **Task 3** — the body part: 13 segments from the VRM table, rest rotations/rolls ported from the
       addon's `freemocap_tpose` **with the name translation** (addon `pelvis`→`hips`, `thigh`→`upper_leg`,
       `face`→`head`, `spine.001`→`chest`, …; `upper_chest`/`toes` authored, provenance stated); ROM
       `None` where the addon has no limit.
4. [x] **Task 4** — hand + face parts; `StandardHuman` rewrite onto composition (55 segments, `dict`-backed
       indices — kills D13's O(n²)).
5. [x] **Task 5** — reference geometry from the T-pose (`origin + basis + length`, no distal point).

Ends: skellyforge suite green (94 tests as of 2026-08-13). **Done** — plus the 4B+5+7 model-rewrite
unit and Task 8 landed in the same sweep, so Phase C below is already complete except the
literature check. `(user)` commit skellyforge when convenient.

### Phase B — the keypoint contract, per tracker (SF-SM Task 6, revised) · skellytracker + skellyforge

Detail in [`09` Task 6](09-segment-model.md#task-6-the-required-keypoint-contract-per-tracker).

6. [x] Absorb the **kept** D7/D8 artifacts (on disk since 2026-08-12) (already on disk — bilateral SC in both body mappings, D39 raise).
7. [x] `test_mapping_completeness.py` — DONE 2026-08-13 (golden fixture + family union with hand side-instantiation; 226 green) — parametrized over all four mappings, asserting each produces every
       name in the model's `required_keypoints()`; plus the load-time raise test (D24's fail-loud half).
       *(Note: `skellytracker/tests/` **exists** — detector tests + conftest; `09` was corrected.)*
8. [x] Add `anatomical_offset` definitions — DONE 2026-08-13 (all five, both mappings, incl. the `eye_width` named length) for `mid_sternum`, `head_vertex`, `foot_ball` — **and `jaw`**
      (the face bones joined the driven contract 2026-08-13) — to **both** body
       mappings, identically (D7's real lesson: every tracker produces the full set, or the model means
       different things per detector).
9. [x] Rename the four YAMLs → `{tracker}_to_standard_human_mapping.yaml` — **done 2026-08-13**:
       the YAMLs, the four detector `standard_human_mapping_path()` methods, `tracker_mapping.py`'s
       vocabulary (incl. D20 typing modernization), and the YAML comment language. **Remaining at the
       commit round:** freemocap's two path-constant dicts call the renamed method
       (`skeleton_rigidifier.py:53`, `center_of_mass.py:62` — they resolve against the *installed*
       skellytracker package, so they update in the same round as the push).

Ends: skellytracker (226 non-video) + skellyforge (94) suites green — **Phase B code done 2026-08-13** →
**Commit Round 1** `(user)`: push skellyforge +
skellytracker, then in freemocap `uv lock --upgrade-package skellyforge` &&
`uv lock --upgrade-package skellytracker` && `uv sync`. Only after this does freemocap's env see the
composed model and the renamed YAMLs.

### Phase C — solver + estimator (SF-SM Tasks 7–8) · **done 2026-08-13** ✅

10. [x] **Task 7** — solver reads declared keypoints (all 55 orientations; no first-child inference; the
        `neck`/`head` crash is load-time validation). Landed as the 4B+5+7 model-rewrite unit.
11. [x] **Task 8** — one median length estimator (`SegmentLengthEstimator`), window-parameterized, keyed
        by segment name; the freemocap duplicate and its test deleted.
12. [ ] **Twist-research check** ([`09` §7](09-segment-model.md#7-open-items)) — confirm the two-tier
        twist design (declared twist keypoint, else damped minimal roll) against
        reconstruction-kinematics best practice. **Re-triggered:** the solver landed without it;
        it now fires before Phase F (VMC consumes `ROTATIONS_LOCAL`), not before Task 7.

Ends: skellyforge suite green — **94 tests as of 2026-08-13**.

### Phase D — retire the old models + rewire the aggregator (SF-SM Task 9) · **DONE 2026-08-13** ✅ (Steps 1–4; → Commit Round 2)

13. [x] Delete `_BONE_TO_LANDMARK`, `_standard_human_cache`, `_get_standard_human()`,
        `_build_solver_positions()` from `realtime_aggregator_node.py:876-1029`; the aggregator loads the
        composed `StandardHuman` and passes keypoints straight through. **This kills the live defect**
        (`ValueError: Bone 'neck' has coincident live proximal and distal joints`).
14. [x] Delete `skellyforge/biomechanics/` (byte-identical duplicate) and `pipelines/dlc_pipeline.py`
        (dead; imports a module that does not exist).
15. [x] Re-express CoM against segments with **de Leva (1996)** — **decided 2026-08-13**: default
        `DE_LEVA_MEAN` (per-sex tables remain available via `segment_inertial_parameters(sex)`); the
        **mass-redistribution policy is kept**; the 8→55 segment mapping is in 09 Task 9 Step 3.
16. [x] **Revised 2026-08-13:** repoint `tracker_schema_message.py` render connections at the composed
        segments now; **delete both YAMLs wholesale in Phase E** (no interim strip — their remaining
        readers die with the posthoc rebuild; the rigidifier re-key is Phase E).

Ends: freemocap realtime runs the composed model end-to-end → `(user)` **Commit Round 2** (freemocap +
skellyforge).

### Phase F — the realtime loop (NOW the next workstream — the user's 2026-08-13 decision) ·

detail plan: [`11-realtime-loop-completion.md`](11-realtime-loop-completion.md) — schema (FMC-WS-3
six-group rework + D34/D35) → encoder + WS reshape (FMC-WS-2 + D36) → frontend decoder/wedge
(FMC-WS-4) → the rigid-body renderer (FMC-RB + D5/D6/D14/D15) → the manual full-loop run, which is
the gate before Phase E. The realtime loop completes BEFORE the posthoc rebuild so posthoc converges
on proven contracts (locked decision 8).

18. [ ] **FMC-WS-3** — `StreamSchema.from_standard_human()` against the six-group layout
        ([`09-standard-stream-protocol`](../09-standard-stream-protocol.md#channels)): ChannelKind rewrite
        (delete legacy `ROTATIONS`, D10), `segment_parents`, frozen (D22), keypoint/segment channel split,
        `SegmentNameString` alias (D29), the schema↔model coupling decision (D30).
19. [ ] Convention fixes — `forward_axis=+X` (D34), verify the camera-0-pinned path meets the +Z/+X
        invariant (D35).
20. [ ] **FMC-WS-2** — encoder + `websocket_server.py` send-path reshape; delete the legacy path and the
        `FREEMOCAP_STANDARD_STREAM` flag in one change (D36).
21. [ ] **FMC-WS-4** — UI wedge: transport service + standard-stream decoder + rolling-window stores.
22. [ ] **FMC-RB** — the rigid-body renderer, with its four defects fixed (index by segment name, not
        parentName D5; cross-section independent of length D6; schema-time index D14; setColorAt once D15).


### Phase E — the posthoc rebuild · **spec written as REVISIT notes; executes AFTER the realtime loop**

detail spec: [`12-posthoc-rebuild.md`](12-posthoc-rebuild.md) — written 2026-08-13, gated on the
manual full-loop run; its §2 decisions (observation.py, the rigidifier re-key) are the user's at the
revisit.

The one piece the re-derivation surfaced as unowned. Locked decision 8 ("realtime and posthoc use the
same computation") makes it mandatory; [`13`](../13-tracker-to-canonical-mapping.md) § Remaining work and
SF-AL's open F4 both named it and no task claimed it.

17. [ ] **Write this phase's own detail plan** (a new `phase-1/NN-` doc) **before any code** — the
        folder's rule. Scope to specify:
        - Route posthoc `Human` through the composed `StandardHuman` + the renamed mappings; retire
          `rtmpose_model_info.yaml` / `mediapipe_model_info.yaml`.
        - Resolve F4: `skellymodels/models/` + `managers/` (~1,500 lines) → composition per SF-AL A7
          (`Actor → Human/Animal/Board` inheritance dies). Blast radius includes
          `skellyforge/pipelines/test_pipeline.py`, which imports `Human`, `Animal` and `ModelInfo`.
        - Disposition of `skeleton_from_mediapipe_observations.py` (144 lines of pre-mapping skeleton
          construction).
        - Decide the `observation.py` silent-fallback imports: keep or fail loudly (handoff open decision).
        - The two-CoM collapse, per Phase D step 15.

Gated on: Round 1 (composed model + renamed mappings reach freemocap's env).

### Phase G — rewrite the docs the old framing infected (SF-SM Task 10)

23. [ ] `13` rewritten as the keypoint → segment reference-geometry boundary; re-declared SSOT for
        **keypoint / segment** (landmark retired).
24. [ ] `00` glossary, `01` frame table, `12` retarget section (+ bilateral SC), `07`/`08` supersession
        records (record, do not delete), `04` decode-flow + `ChannelKind`, `05` overlay toggle note, `02`
        reprojection scope note.

---

## 3. Commit rounds (user-owned — never touched by the agent)

| Round | After | Pushes | Then |
|---|---|---|---|
| 0 | §1 disposition | skellyforge revert + kept skellytracker files (or revert-vs-commit as the user prefers) | — |
| 1 | Phase B | skellyforge + skellytracker — **pushed + synced 2026-08-13** ✅ | freemocap: `uv lock --upgrade-package skellyforge skellytracker` + `uv sync` done. **Leftover (rides with Task 9 Step 1):** the two mapping-path dicts → `standard_human_mapping_path()`, the `RollingBoneLengths` → `SegmentLengthEstimator` import, and the aggregator's deleted-symbol imports — the env is new, the code is old |
| 2 | Phase D | freemocap + skellyforge | unblocks E/F on the real model |
| … | each phase end | as the user decides | — |

## 4. Open decisions carried forward (with triggers)

| Question | Trigger |
|---|---|
| Twist-resolution best-practices check (Phase C step 12) | before Phase F — VMC consumes `ROTATIONS_LOCAL` |
| CoM mass-redistribution capability — survives or is dropped? | Phase D step 15 |
| `observation.py` silent-fallback imports — keep or fail loudly? | Phase E detail plan |
| ROM enforcement design (closed-form clamp ≠ constraint iteration) | after the model lands |
| `.VRM` export (needs skinned mesh) | its own plan, after SF-SM |
| Face blendshapes driven from tracked landmarks | `[LATER]` |
| Disabled centroidal kinematics aligned to the new models | `[LATER]` |
| Freemocap full-suite runtime failures (E2E etc.) | deferred by the user — separate task |

## 5. Definition of done (whole project)

- One segment model in skellyforge; the composed standard human is **55 segments**, matching `BONE_ALIASES`.
- Every segment produces an orientation; no silent skips, no first-child inference; the live `neck`/`head`
  crash is impossible (validation at load) and its bridges are deleted.
- Every tracker mapping produces the full required keypoint set; a gap fails at load; the mapping files no
  longer say "canonical".
- Realtime and posthoc share one computation and one length estimator; posthoc is not degraded.
- `canonical_body.yaml`'s graph stack, `_BONE_TO_LANDMARK`, `proximal_landmark`, the aggregator bootstrap,
  `biomechanics/`, `dlc_pipeline.py`, and the `Actor → Human/Animal/Board` inheritance are gone.
- The stream schema derives from the composed model; the convention says `+X` forward; the legacy wire path
  and its flag are deleted.
- The docs speak **keypoint / segment** only; `13` is SSOT for the boundary.
