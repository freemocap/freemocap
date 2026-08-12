# 14 — Engine Testing Strategy

> Sister to [08 — Testing Strategy](08-testing-strategy.md). **08 owns the wire; this doc owns the math.**
> The kinematics engine in SkellyForge — quaternion algebra, coordinate frames, the orientation solver — and
> the `anatomical_offset` mapping form in SkellyTracker. Everything upstream of serialization.
>
> Status: **specification.** The suite does not exist yet; this doc is what it is built against.

## Why this doc exists

[08](08-testing-strategy.md) is thorough about the wire and says nothing about the math, so **nothing owned
the engine tests** and none were written. Roughly 3,200 lines of new math landed in
`skellyforge/kinematics/` and `standard_human/`, plus 466 in skellytracker's `tracker_mapping.py`, with
`pytest` collecting zero tests in either repo. Meanwhile FreeMoCap has 23 tests, all covering the
msgspec/numpy round-trip — the part least likely to be silently wrong.

That gap is not hypothetical. It is how the parent-relative quaternion composition shipped with reversed
operands ([AUDIT_2026-08-12 §3.1](AUDIT_2026-08-12.md#31-local-quaternion-composition-order)), behind a test
that passed.

The engine has a failure mode the wire does not: **it produces plausible numbers.** A reversed quaternion
product still yields a unit quaternion of the right magnitude. A sign-flipped basis is still orthonormal. A
mis-scaled offset still lands somewhere anatomically believable. Nothing crashes, nothing looks obviously
wrong, and the error surfaces three layers downstream as an avatar in a horrifying pose. So the tests here
are written to pin **conventions and invariants**, not to check that functions run.

## The rule that governs every test below

**A test must be able to fail for the reason it exists.**

The cautionary case is the SF-SH-4 check that validated parent-relative rotation with a *uniform* bend —
every segment rotated identically. When `q_child == q_parent`, both `conj(q_p) · q_c` and `q_c · conj(q_p)`
reduce to identity, so the test passed under either operand order. It read as coverage while being
structurally blind to the one thing it was there to catch.

Concretely, this means:

- **Asymmetric fixtures.** Different rotations about different axes for parent and child. Never a uniform
  transform, never a single-axis rotation, when the property under test is order- or axis-sensitive.
- **Guard the guard.** Where a fixture has to have a property for the test to mean anything, assert that
  property as its own test. Building the composition suite turned up **three independent ways** a
  parent/child pair goes order-blind (see §2); each was found only because the previous fixture silently
  passed half its assertions. A fixture invariant that is only in a comment will be edited away.
- **Round-trips over spot values.** `recompose(parent, local) == child` pins the convention; a hand-computed
  expected quaternion pins one sample of it.
- **Named component order, always.** Every literal quaternion in a test states `wxyz`. Identity is
  `(1, 0, 0, 0)`. Three.js and Unity use `xyzw` and the swap is silent —
  [01](01-canonical-data-model.md#the-rest-pose--t-pose-reference) asserted the rest-pose contract in `xyzw`
  by mistake for exactly this reason.
- **Sign and handedness asserted explicitly**, not inferred from magnitude.

## Test infrastructure

**SkellyForge has none.** `skellyforge/tests/` does not exist and `pytest` collects nothing (the only
`test_*.py` in the tree is an unrelated pipeline file). Standing it up is the first deliverable.

- `skellyforge/tests/` with pytest config; the engine suite runs with numpy + pydantic only — no heavy
  optional dependencies, so it stays fast and CI-cheap.
- `skellytracker/tests/` likewise, for `tracker_mapping.py`.
- **Cross-repo caveat.** SkellyForge and SkellyTracker changes verify in **their own** environments and are
  invisible to FreeMoCap until the user commits and pushes, then `uv lock --upgrade-package <pkg>` +
  `uv sync`. See `project/CLAUDE.md` and [`HANDOFF_GUIDE`](HANDOFF_GUIDE.md). A green engine suite in
  SkellyForge does **not** mean FreeMoCap is running that code.

## 1. Quaternion algebra

`skellyforge/kinematics/quaternion_math.py`.

- **Hamilton product semantics.** Assert the documented contract `R(q₁ · q₂) = R(q₁) ∘ R(q₂)` — `q₂` applied
  first — by rotating a vector both ways and comparing. Assert **non-commutativity** with a case where
  `q₁ · q₂ ≠ q₂ · q₁`, so the property is pinned rather than assumed.
- **Conjugate is inverse** for unit quaternions: `q · conj(q) == identity`.
- **Rotation-matrix round-trip** through all four branches of `from_rotation_matrix`. Shepperd's method
  selects a branch on the trace and the largest diagonal element, so a single test rotation exercises one
  branch and leaves three unverified. Cover each deliberately, including the near-180° cases where the
  branch choice is load-bearing.
- **SLERP:** endpoints exact at `t=0` and `t=1`; constant angular rate across the interval; shortest-arc
  selection under the double cover (`q` and `−q` are the same rotation, and the wrong choice takes the long
  way round); the near-parallel fallback where `sin θ` vanishes.
- **Normalization on construction** contains drift rather than accumulating it.

## 2. Composition convention — the decisive one

This is the suite's reason for existing. Convention per
[07 § Segment rotation conventions](07-coordinate-conventions.md#segment-rotation-conventions):
`q_world` maps segment-frame → world, therefore

```
q_child_world = q_parent_world · q_child_local
q_child_local = conj(q_parent_world) · q_child_world
```

> **Status: implemented — 22/22 green.** `skellyforge/tests/test_quaternion_composition.py` (convention in
> isolation, 12 tests) and `test_orientation_solver_composition.py` (the solver's actual output, 10 tests).
> The suite went red first — 4/4 composition assertions failing — which confirmed
> [D1](phase-1/07-spec-reconciliation.md#10a-correctness) empirically rather than by reading docstrings, and
> only then was the solver corrected. That order matters: the test decided the convention, it did not
> ratify a change already made.

### The three ways a pair goes order-blind

A parent/child pair proves nothing about operand order if **any** of these hold. All three were found while
building this suite, each by a fixture that silently passed half its assertions:

1. **Uniform bend** — `q_child == q_parent`, so both orders reduce to identity. The known case; it is what
   let D1 ship.
2. **Either segment at its rest orientation** — its world quaternion is identity, and
   `conj(I) · q == q · conj(I)`. An identity *parent* or an identity *child* is equally fatal.
3. **Coaxial rotations** — parent and child rotated about the same axis **commute**. Distinct segment
   *directions* are not the invariant; distinct **rotation axes** are. This is the subtle one: a fixture can
   look thoroughly asymmetric in world space and still be coaxial from rest.

Each is a **guard test** in the suite, so a future fixture edit that reintroduces one fails loudly instead
of quietly reducing coverage.

- **Differential-bend test.** Parent rotated about one axis, child about a different axis by a different
  magnitude. Assert the returned local quaternion matches the hand-derived value **including axis**. The
  reversed order produces the correct angle about the *wrong axis*, so an angle-only assertion passes it.
- **Round-trip.** For every segment: `recompose(parent_world, local) == child_world` within tolerance,
  walking the full hierarchy from root. This pins the convention structurally instead of sampling it, and it
  is the assertion that would have caught the shipped bug.
- **Root case.** Root local == root world, since there is no parent.
- **Identity cases**, kept but *not* relied upon: all-identity input → all-identity output; uniform bend →
  identity locals. Both are true and both are blind to operand order — they belong in the suite as sanity
  checks and must never be the only coverage.
- **Chain depth.** A three-deep chain (hips → spine → chest) with distinct rotations at each level, so an
  error that cancels between two levels cannot hide.

## 3. Coordinate frames and Kabsch

`skellyforge/kinematics/coordinate_frame_ops.py`.

- **`build_orthonormal_basis`:** rows orthonormal to tolerance; **right-handed** (`det == +1`, not `−1` —
  a left-handed basis is still orthonormal and silently mirrors everything downstream); the third axis
  equals `cross(exact, approximate)` normalized.
- **Near-parallel rejection.** `CoordinateFrameDefinition.__post_init__` rejects axes within ~1°. Assert it
  raises rather than returning a degenerate basis, and assert the boundary either side of the threshold.
- **`rotation_between_vectors`** is swing-only: it aligns the long axes and leaves twist free. Assert it maps
  `from` onto `to` exactly, and assert it is **minimal** — the rotation axis is perpendicular to both
  vectors, i.e. no twist has been introduced. Include the antiparallel case, where the axis is
  underdetermined and a naive cross product is zero.
- **`align_point_sets_kabsch`:** exact recovery from a known rotation applied to a synthetic point set;
  graceful degradation under added noise; **reflection rejection** — the SVD's sign correction must prevent
  a mirrored solution, which is the classic Kabsch trap and produces a skeleton that is subtly inside-out.
- **`compute_rotation_from_live_basis`** round-trips: build a live basis by rotating a reference basis with a
  known quaternion, recover it, compare.

## 4. Orientation solver

`skellyforge/kinematics/orientation_solver.py`.

- **Identity at T-pose.** Feed the model's own rest geometry as live input; every segment must return
  identity. This is the `identity == T-pose` contract
  ([01](01-canonical-data-model.md#the-rest-pose--t-pose-reference)) and every downstream adapter assumes it.
- **Twist-tier dispatch.** One test per tier asserting the tier actually taken, not merely a plausible
  result: `FULL_FRAME` with ≥3 non-collinear points; `CHAIN_RESOLVED` recovering a known roll from the child
  direction; `DAMPED_MINIMAL` when no twist source exists.
- **Twist recovery is the point of the chain-resolved tier** — rotate a segment about its own long axis with
  the child direction held informative, and assert the roll is recovered. A swing-only solver passes any test
  that only checks the long axis, which is why the long axis is not sufficient evidence here.
- **Singularity gate.** Sweep the parent/child angle through the ~5° threshold and assert the tier degrades
  to damped-minimal on the correct side, and that no discontinuity appears in the output as it crosses.
- **Fallback paths still damp.** Per [12](12-standard-human-model.md) and defect D3, a fallback triggered by
  occlusion or the singularity gate must still receive previous-frame state. Assert damping is applied on
  every fallback path — the current code passes `previous=None` there, so damping is skipped in exactly the
  case it exists for.
- **Degenerate inputs raise.** Zero-length segments, NaN positions, missing required segments — fail loudly,
  per [00](00-overview.md). Assert the exception, not a silently-identity result.

## 5. Critical damping

Specified in [12 § twist policy](12-standard-human-model.md#per-segment-twist-policy-the-underdetermined-roll-plan).

- **Framerate independence.** The damping parameter is a **time constant in seconds**, not a per-frame blend
  factor. Run the same motion at 30, 60 and 120 fps and assert the settling time in *seconds* matches. A
  per-frame factor fails this, which is the bug the specification change exists to prevent.
- **No overshoot.** Critically damped means exactly that: step the target and assert the response approaches
  it monotonically. A second-order filter that overshoots is under-damped and has been mis-tuned; a
  first-order lag never overshoots but also is not critical damping, so pair this with the settling-time
  assertion.
- **Settling time** matches the declared time constant.
- **First frame and gaps.** No previous state → return the current value undamped. After a gap, do not
  integrate stale velocity across it.
- **Reset** clears the state; damping does not carry across recordings.

## 6. `anatomical_offset`

`skellytracker/core/io/tracker_mapping.py`.

- **Determinism.** Identical keypoints in → identical landmark out, every time. No fitting, no iteration,
  no hidden state.
- **Subject scaling is linear.** Scale every input keypoint by `k` and the offset magnitude scales by `k`,
  because it is an anthropometric ratio of a reference length.
- **Anterior sign.** With `up = hips_center → neck_center` and `lateral = left_shoulder → right_shoulder`,
  `anterior = up × lateral` must point in the subject's facing direction. Assert at **several arbitrary
  subject facings in the ground plane**, not one — a single facing can pass by coincidence. (Verified
  manually at 0°/37°/90°/180°/265° during FMC-SR; this test makes it permanent.)
- **Handedness dependence is explicit.** The sign above holds *because* the canonical basis is right-handed
  ([07](07-coordinate-conventions.md)). Assert it, so a future change to the calibration basis fails here
  rather than silently mirroring anatomy.
- **Frame construction** matches `CoordinateFrameDefinition`: exact axis preserved, approximate axis
  orthogonalized, third by right-handed cross product.
- **Rest-pose and live-frame agreement.** The same definition places the T-pose landmark and the per-frame
  landmark. Assert one function, both uses — divergence here is what makes `identity == T-pose` quietly
  false.
- **Missing keypoints.** Per [13](13-tracker-to-canonical-mapping.md), a landmark whose sources are missing
  *this frame* is omitted (occlusion is data, not an error), but a mapping referencing a keypoint the tracker
  **never** produces must raise **at load**. Assert both halves — they are easy to conflate and the
  distinction is what keeps [00](00-overview.md)'s fail-loud principle honest.

## 7. Standard human model

`skellyforge/skellymodels/standard_human/`.

- **Validators reject what they claim to reject:** duplicate names, multiple roots, missing parents, cycles,
  twist sources pointing at absent segments. One test per validator, each asserting the raise.
- **Hierarchy accessors** agree with each other — `segment_parents`, children, and root-to-segment chains
  describe the same tree.
- **Every segment resolves a usable direction.** No segment may have its origin and its first child's origin
  at the same point; that yields a zero-length vector and a permanently-identity rotation. The realtime
  bootstrap has three such segments today, which is a silent hole rather than a failure.
- **Handedness survives mirroring.** After composition, assert `det(basis) == +1` for **every** segment on
  **both** sides. Mirroring reflects rest positions (negating Y, the sagittal normal) and then *rebuilds*
  each frame right-handed; reflecting a basis directly would give `det == -1` and silently invert every
  construction that assumes right-handedness — including `anterior = up × lateral`. A left-handed frame is
  still orthonormal, so nothing else would catch it. See
  [SF-AL A3](phase-1/08-skellyforge-alignment.md#a3--mirroring-reflect-positions-rebuild-frames).
- **Composition expands to the authored structure.** A part instantiated twice must produce two
  structurally identical segment sets under different prefixes, joined to the host tree by name agreement —
  and the generated flat list must contain no segment absent from the composed definition.
- **Blendshape channels are the declared 52** ([12](12-standard-human-model.md), locked decision 4).
- **Alias round-trip:** every canonical name resolves for every declared target, and `resolve_alias` falls
  back to the canonical name for missing entries rather than raising.

## What this doc does not cover

The wire — golden bytes, loopback, LSL pass-through, coordinate-converter vectors, third-party conformance.
Those are [08](08-testing-strategy.md). The boundary is serialization: once a quaternion is correct and in
the canonical convention, 08 owns getting it onto the wire intact.

## Definition of done

- `skellyforge/tests/` and `skellytracker/tests/` exist and collect.
- Sections 1–7 have coverage, with §2's differential-bend and round-trip cases landing **before** any fix to
  the composition order — the test decides the convention empirically rather than confirming a reading of
  the docstrings.
- No test in the suite passes under both operand orders, both handedness conventions, or both component
  orders. If one does, it is not testing what it claims.
