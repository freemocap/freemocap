# 12 — Posthoc Rebuild (Phase E) — spec written as REVISIT notes

> **Status: SPEC ONLY — do NOT execute until the realtime loop is closed**
> ([`11-realtime-loop-completion.md`](11-realtime-loop-completion.md), the user's sequencing decision
> 2026-08-13). This doc is written now so the scope is captured while it is fresh; it is **revisited
> and revised after the realtime loop's manual full-loop run**, which is the gate. Anything the
> realtime loop shakes out (schema details, the encoder's keypoint handling, the rigidifier's re-key
> shape) lands in §7 before execution begins.
>
> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` when executing — after the revisit. Steps use
> checkbox (`- [ ]`) syntax. **No code until the revisit.**

**Why posthoc waits:** locked decision 8 — *realtime and posthoc use the same computation*. Posthoc
must converge on the contracts the realtime loop proves (the composed model, the mappings, the de
Leva CoM, the schema), not on guesses about them. Rebuilding posthoc first would mean reworking it
after F.

**Goal:** The posthoc `Human` pipeline consumes the same composed `StandardHuman` + the renamed
mappings + the same segment computation as realtime; the old model layer
(`skellymodels/models/` + `managers/`, the legacy tracker model-infos, the canonical YAMLs) is
deleted, not ported.

---

## 1. What posthoc does today (and what each piece becomes)

| Today (posthoc) | Reads | Becomes |
|---|---|---|
| `Human` actor (`skellymodels/managers/human.py`, `Actor → Human/Animal/Board`) | legacy tracker model-infos (`rtmpose_model_info.yaml` / `mediapipe_model_info.yaml`) + `ModelInfo`/`AnatomicalStructure` | the composed `StandardHuman` + the renamed mappings; the inheritance dies (SF-AL A7) |
| `AnatomicalStructure` / `ModelInfo` / `Aspect` / `Trajectory` (~1,500 lines) | `canonical_body.yaml` / `canonical_hand.yaml` | deleted — segments are the model now |
| `enforce_rigid_bodies` (the addon-derived median-length enforcement) | `bone_length_ratios` + per-bone medians | the shared `SegmentLengthEstimator` (unbounded window = the batch median) + the model's declarations — **the realtime rigidifier is already re-keyed by F0; posthoc converges on the same shape** |
| batch CoM (`skellymodels/biomechanics/calculations/…`) | Winter tables from the YAML | the SAME de Leva spans as realtime (Phase D's rewrite is the single computation — posthoc imports it, no second implementation) |
| `skeleton_from_mediapipe_observations.py` (144 lines) | pre-mapping skeleton construction | deleted — the mapping + model replace it |
| batch diagnostics (`kinematics/segment_lengths.py` + the freemocap CLI wrapper `segment_length_io.py`) | `bone_length_ratios` | re-keyed onto the model's segment `length_ratio`s (labels become segment names) |
| `skellyforge/pipelines/test_pipeline.py` | `Human`, `Animal`, `ModelInfo` | rewritten or deleted with the layer it tests |
| `data_models/observation.py` | runtime `try`/`except` fallback imports of skellytracker | the decision below |

## 2. The decisions to make at the revisit (not now)

1. **`observation.py` silent-fallback imports — keep or fail loudly?** The fallback rebinds
   skellytracker types to `str`/`np.ndarray`/shims on `ImportError`. Keeping it violates fail-loud;
   removing it makes skellyforge depend on skellytracker at import time (the import-rule-3 tension).
   Options: (a) delete the shims and import skellytracker for real (rule 3 says "don't let it block"),
   (b) delete the module's skellytracker coupling entirely if its only consumer (posthoc observation
   loading) dies with the rebuild. Decide with the actual consumer map in hand.
2. ~~The realtime rigidifier's re-key~~ — **resolved 2026-08-13: moved to F0 of the realtime
   loop** ([`11`](11-realtime-loop-completion.md)) — the user's call. Phase E inherits the re-keyed
   rigidifier; the live path carries no old-layer dependency by the time this doc executes.
3. **`skeleton_from_mediapipe_observations.py`** — verify zero realtime importers, then delete
   (posthoc rebuilds from the mappings).
4. **Two-CoM collapse** — posthoc switches to the shared de Leva computation (Phase D); the old batch
   Winter implementation is deleted with the old layer. No capability is lost: the redistribution
   lives in the shared path.

## 3. The task outline (execution order after the revisit)

- [ ] **E1 — the shared posthoc model + mapping pipeline:** posthoc loads
      `compose_standard_human()` + the renamed mappings (per detector); observations attach by
      keypoint name (SF-AL A6 — the model layer knows nothing about trackers); the legacy tracker
      model-infos are retired.
- [ ] **E2 — the old layer dies:** `models/` + `managers/` deleted per A7 (composition replaces the
      `Actor → Human/Animal/Board` inheritance); `canonical_body.yaml` / `canonical_hand.yaml`
      deleted wholesale (the revised Task-9 Step-4 decision — no interim strip); `pipelines/test_pipeline.py`
      rewritten or deleted. (The rigidifier re-key already landed in F0 — nothing to do here.)
- [ ] **E3 — shared computations wired:** `enforce_rigid_bodies` → the shared
      `SegmentLengthEstimator` (unbounded = batch median); batch CoM → the shared de Leva path;
      batch diagnostics re-keyed onto segment names.
- [ ] **E4 — `observation.py` per decision 1; `skeleton_from_mediapipe_observations.py` per
      decision 3.**
- [ ] **E5 — parity proof:** the posthoc pipeline and the realtime pipeline, given the same
      recording, produce the same segment orientations (the locked-decision-8 test — batch solve ==
      streaming solve at matched windows).

## 4. What this doc deliberately does NOT cover

- The parquet/tidy serialization rework ([`../10`](../10-serialization-and-tidy-format.md)) — its own
  later plan.
- The Blender addon, the VMC/streaming adapters (Phase F is the loop; adapters come after).
- `bvh_exporter/advanced_bvh_rotation.py` — decide in the revisit (vestigial; likely deleted when
  the shared engine replaces it).

## 5. Definition of done (posthoc)

- One model layer. `models/` + `managers/`, the legacy model-infos, the canonical YAMLs, and the
  pre-mapping skeleton construction are gone.
- Posthoc and realtime share the composed model, the mappings, the length estimator, and the de Leva
  CoM — and the parity test (E5) pins it.
- No silent-fallback imports (per the decision).
- Suites green: skellyforge (with the layer gone), freemocap posthoc tests, the realtime suites
  still green.

## 6. Handoff notes for whoever reopens this

- The realtime loop ([`11`](11-realtime-loop-completion.md)) is the gate — its F5 manual run is the
  trigger to reopen this doc.
- Re-read the Phase-D progress entries in
  [`../IMPLEMENTATION_PLAN.md`](../IMPLEMENTATION_PLAN.md) for what already converged (the de Leva
  CoM, the schema's minimal adaptation, the aggregator rewiring).
- The decisions in §2 are the user's — present them with the consumer maps, don't assume.

## 7. Revisit checklist (fill in after the realtime loop)

- [ ] What the manual full-loop run changed about the model/solver/stream contracts
- [ ] The schema's final shape (F1's outcomes) — anything posthoc must mirror
- [x] The rigidifier re-key — resolved: landed in F0 (before the loop's manual run)
- [ ] The encoder's keypoint handling (F2) — posthoc's serialization parity target
- [ ] `observation.py`'s actual consumer map (who still imports it after E1–E3)
- [ ] New defects the loop surfaced (→ the defect register in
      [`07-spec-reconciliation.md`](07-spec-reconciliation.md))
