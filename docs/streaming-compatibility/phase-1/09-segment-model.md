# SF-SM — Segment Model (VRM 1.0 rigid bodies from tracker keypoints)

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development` (recommended)
> or `superpowers:executing-plans` to implement this task-by-task. Steps use checkbox (`- [ ]`) syntax.
>
> **Status: plan for agreement — no code until agreed.**
>
> **This supersedes the keypoint→landmark framing.** [`13`](../13-tracker-to-canonical-mapping.md) declared
> itself SSOT for a *keypoint / landmark / segment* distinction in which landmarks were an intermediate
> layer that a model got fitted to. That layer is obsolete — as is the "canonical keypoint" set that
> inherited its role. **The boundary is keypoint → segment reference geometry:** segment definitions
> reference keypoints **directly by name** to define their origin / long-axis / twist axes; there is no
> intermediate canonical-keypoint or landmark layer. Task 10 rewrites `13` and the docs that inherited
> the old framing.
>
> **Whole-project ordering + the D7/D8 disposition:** [`10-whole-project-alignment.md`](10-whole-project-alignment.md).

**Goal:** One segment model in SkellyForge — VRM-1.0-aligned rigid bodies whose reference geometry is
defined directly from tracker keypoints — replacing the three partial human models that exist today.

**Architecture:** A segment is a rigid body with an **origin**, an **orientation**, and a **length**. All
three are declared per segment as *named keypoints* plus a rest pose; one declaration is
evaluated twice — against the T-pose to build the reference geometry, and against each frame to read the
live pose. Parts (body, hand, face) are authored once and instantiated per side. The solver walks the tree
once and emits origins **and** quaternions.

**Tech stack:** Python 3.11+, numpy, pydantic (model), dataclasses (hot path), pytest. No new dependencies.

---

## 1. Why this exists

Three human models exist in SkellyForge and none of them is the one the kinematics engine wants:

| # | what | consumed by | problem |
|---|---|---|---|
| A | `canonical_body.yaml` / `canonical_hand.yaml` + `AnatomicalStructure`/`ModelInfo` | CoM, render connections, posthoc `enforce_rigid_bones` | pre-dates the kinematics work; encodes one graph three ways; 2 segments reversed, 3 are non-tree chords |
| B | `skellymodels/standard_human/` (`HumanBone`, `StandardHuman`) | the orientation solver | never loads A; bootstrapped **inside the FreeMoCap aggregator** |
| C | `skellymodels/models/` + `managers/` (~1,500 lines) | posthoc `Human` | zero references to B |

Measured against A and B: they share **11 of 25** body segment names and **9 of 20** hand names. They are
not two encodings of one model — B is VRM rigid bodies, A is a landmark graph whose `segment_connections`
includes `head` = `left_ear → right_ear` (a width chord, not an orientable body).

The newest code already speaks the right language: across `skellyforge/kinematics/` and
`standard_human/`, "landmark" survives only in prose and in **one** field — `HumanBone.proximal_landmark`.
Both remaining bridges (`proximal_landmark`, and its FreeMoCap counterpart `_BONE_TO_LANDMARK`) are
artifacts of the retired landmark layer, already obviated by the keypoint → reference-geometry design —
they are **deleted, not ported** (decision 10). The live defect they currently cause is the proof the
bridge must not survive: `_BONE_TO_LANDMARK` maps `neck` and `head` to the same point (`head_center`), so
the solver raises `ValueError: Bone 'neck' has coincident live proximal and distal joints` on any frame
containing `head_center`, and there is no `try`/`except` in the aggregator frame loop. Tasks 1 + 9 close
it: validation at model load, then deletion.

**Reference implementation.** The FreeMoCap Blender addon's armature pipeline solves this problem and its
output is known-good. Its vocabulary is obsolete (MediaPipe names, `spine.001`, `f_index.01.R`) and is
**not** carried over — only the structure is.

| Blender | what it does | becomes |
|---|---|---|
| `CopyLocationConstraint(target)` | pins bone head to a keypoint | `origin_keypoint` |
| `DampedTrackConstraint(target, TRACK_Y)` | aligns the long axis, roll free | `long_axis_keypoint` |
| `LockedTrackConstraint(target, lock_axis)` | rotates about the long axis to point another axis at a keypoint | `twist_keypoint` |
| `LimitRotationConstraint(min/max XYZ, LOCAL)` | joint ROM limits | `rotation_limits` (declared, not yet enforced) |
| bone `roll` | rest twist about the long axis | `rest_roll` |
| `ArmatureBoneInfo.parent_position: head\|tail` | which end the child attaches to | `parent_attachment` |
| `calculate_bone_length_statistics` median | subject scale | the length estimator (Task 8) |

The decisive borrow: **twist is sourced from a named keypoint, not from a child segment's direction.**
Today's `TwistPolicy.twist_source_bone` can only borrow a child's long axis, which is why `head`, both
hands and both toes produce no orientation at all (no children) and why `neck` crashes. Declaring a twist
keypoint makes every segment solvable.

**Twist resolution is two-tier, and both tiers are already proven in code.** Where a segment declares a
twist keypoint, roll resolves from that keypoint (the addon's `LockedTrack` analogue). Where it does
**not**, the solver falls back to the **damped minimal-twist** tier — hold rest roll and critically damp,
i.e. *minimize roll drift* rather than invent one. That fallback is the existing `DAMPED_MINIMAL` tier
with the critically damped filter (D3/D4, 51 green tests); SF-SM keeps it, it does not re-derive it.
Before Task 7, the two-tier design is checked against reconstruction-kinematics best practice — see
[§7](#7-open-items).

## 2. Decisions (locked 2026-08-12 — do not re-litigate)

1. **A segment is origin + orientation + length.** Not proximal+distal. `BoneReferenceGeometry` currently
   stores the long-axis direction twice — as `distal - proximal` **and** as `CoordinateFrameDefinition.exact_axis`
   — and `exact_axis` is never read by the solver. `distal_joint_center` is derived: `origin + length × long_axis`.
2. **Length is the third component, not adjacent tooling.** With origin+orientation the chain only closes
   if the length is right; a correct humerus rotation still puts the elbow in the wrong place at the wrong
   length.
3. **One declaration, evaluated twice** — T-pose reference geometry and live per-frame pose. This is the
   property [`13`](../13-tracker-to-canonical-mapping.md) already states for `anatomical_offset`,
   generalized to the whole segment.
4. **The T-pose is a fixed table of orientations × per-subject measured lengths.** VRM 1.0 has **no**
   numeric rest geometry — its `humanoid.md` "Estimated Position" column is anatomical prose
   (`hips`→Crotch, `leftLowerArm`→elbow). The orientations port from the addon's `freemocap_tpose`
   (`rotation` euler + `roll`); the lengths are measured.
5. **Full VRM 1.0 humanoid: 55 segments.** Body + hands + face. Not a subset. Parts authored once,
   instantiated per side.
6. **Derive, don't omit.** If a VRM segment can be determined for a given tracker — directly or via
   `anatomical_offset` — it is. This is per-tracker work.
7. **ROM limits are specified now, computed later.** Declared on the segment; the solver ignores them in
   this workstream.
8. **Realtime and posthoc use the same computation.** The only difference is information available
   (streaming window vs whole recording). No deliberate fidelity downgrade.
9. **VRM 1.0 snake_case names throughout.** No MediaPipe vocabulary, no Blender bone names.
10. **`_BONE_TO_LANDMARK`, `HumanBone.proximal_landmark`, and the aggregator bootstrap are deleted**, not
    ported.

## 3. The boundary contract

```
SkellyTracker                      │  the boundary  │            SkellyForge
                                   │                │
 tracker keypoints ──[ {tracker}_keypoint_mapping.yaml ]──▶ named keypoints
 (COCO-WholeBody, MediaPipe;       │                │   (direct, mean-derived, offset)
  per-detector names)              │                │                    │
                                   │                │                    ▼
                                   │                │        segments declare which
                                   │                │        keypoints define their
                                   │                │        origin / long axis / twist
```

**There is no intermediate canonical-keypoint or landmark set.** Keypoints are keypoints: some come
straight from the detector, some are derived per tracker (a mean like `hips_center`, an
`anatomical_offset` like `sternoclavicular`) — and the segment model references them **directly by name**
to define its reference-geometry axes. SkellyForge owns the declaration ("which keypoints does each
segment need"); SkellyTracker owns the guarantee that every named keypoint is actually produced, however
the detector has to produce it.

**The model publishes the keypoint names it requires; every tracker mapping must produce all of
them.** A mapping that cannot is an error **at load**, not a silent omission. (A keypoint missing *this
frame* is occlusion — still data, still skipped. Both halves per
[`13`](../13-tracker-to-canonical-mapping.md) / defect D24.)

Keypoint names are side-agnostic within a part — the hand mappings already emit `wrist`, `thumb_cmc`, …
with no side prefix, so a hand instantiated with prefix `left_` yields `left_wrist`, which is already the
body's wrist. Parts join by name agreement (SF-AL A2). The mapping files themselves are renamed to drop
the retired "canonical" vocabulary — `{tracker}_keypoint_mapping.yaml` (Task 6).

## 4. File structure

**Create — `skellyforge/skellymodels/standard_human/`:**

| File | Responsibility |
|---|---|
| `segment_definition.py` | `SegmentDefinition`, `RotationLimits`, `ParentAttachment` — the authored unit |
| `segment_parts.py` | `SegmentPart` (a named, side-agnostic set of segments) + `compose_parts()` |
| `body_part.py` | the body part: 22 segments, authored once |
| `hand_part.py` | the hand part: 16 segments, authored once, instantiated twice |
| `face_part.py` | eyes + jaw segments (declared, undriven) + the 52 blendshape channels |
| `standard_human_model.py` | **[rewrite]** `StandardHuman` — composed parts → flat indexed segment list |
| `reference_geometry.py` | `SegmentReferenceGeometry` (origin + basis + length) + `build_reference_geometry()` |

**Modify:**

| File | Change |
|---|---|
| `skellyforge/kinematics/orientation_solver.py` | read declared origin/long-axis/twist keypoints; delete `_get_distal_position` |
| `skellyforge/kinematics/online_segment_lengths.py` | one median estimator, window-parameterized (Task 8) |
| `skellyforge/skellymodels/standard_human/human_bones.py` | **[retire]** superseded by `segment_definition.py` |
| `freemocap/core/pipeline/realtime/realtime_aggregator_node.py:876-1029` | delete `_BONE_TO_LANDMARK`, `_get_standard_human`, `_build_solver_positions` |

**Delete:** `skellyforge/biomechanics/` (F5, byte-identical, zero importers); `skellyforge/pipelines/dlc_pipeline.py`
(imports `skellyforge.triangulation`, which does not exist — the module cannot import and nothing imports it).

**Tests — `skellyforge/tests/`:** `test_segment_definition.py`, `test_part_composition.py`,
`test_reference_geometry.py`, `test_solver_keypoint_declared.py`, `test_segment_length_estimator.py`.

---

## 5. Tasks

### Task 1: `SegmentDefinition` — the authored unit

**Files:**
- Create: `skellyforge/skellymodels/standard_human/segment_definition.py`
- Test: `skellyforge/tests/test_segment_definition.py`

- [x] **Step 1: Write the failing test**

```python
# skellyforge/tests/test_segment_definition.py
import math
import pytest
from skellyforge.skellymodels.standard_human.segment_definition import (
    ParentAttachment, RotationLimits, SegmentDefinition,
)

def _upper_arm(**overrides) -> SegmentDefinition:
    kwargs = dict(
        name="upper_arm",
        parent="shoulder",
        parent_attachment=ParentAttachment.DISTAL,
        origin_keypoint="shoulder",
        long_axis_keypoint="elbow",
        twist_keypoint="wrist",
        rest_rotation=(0.0, math.radians(90.0), 0.0),
        rest_roll=math.radians(90.0),
        length_ratio=0.186,
        rotation_limits=RotationLimits(x=(-135.0, 90.0), y=(-98.0, 180.0), z=(-97.0, 91.0)),
    )
    kwargs.update(overrides)
    return SegmentDefinition(**kwargs)

def test_required_keypoints_lists_all_three_roles():
    assert _upper_arm().required_keypoints() == {"shoulder", "elbow", "wrist"}

def test_required_keypoints_omits_absent_twist_source():
    assert _upper_arm(twist_keypoint=None).required_keypoints() == {"shoulder", "elbow"}

def test_resolves_twist_is_true_only_when_a_twist_keypoint_is_declared():
    assert _upper_arm().resolves_twist is True
    assert _upper_arm(twist_keypoint=None).resolves_twist is False

def test_origin_and_long_axis_keypoints_must_differ():
    # This is the `neck`/`head` bug: two roles naming one point yields a zero-length
    # segment vector, and no orientation can be resolved from it.
    with pytest.raises(ValueError, match="origin_keypoint and long_axis_keypoint"):
        _upper_arm(long_axis_keypoint="shoulder")

def test_twist_keypoint_must_differ_from_the_long_axis_keypoint():
    with pytest.raises(ValueError, match="twist_keypoint"):
        _upper_arm(twist_keypoint="elbow")

def test_name_must_be_snake_case():
    with pytest.raises(ValueError, match="snake_case"):
        _upper_arm(name="upperArm")

def test_length_ratio_must_be_positive():
    with pytest.raises(ValueError, match="length_ratio"):
        _upper_arm(length_ratio=0.0)

def test_length_ratio_must_be_finite():
    with pytest.raises(ValueError, match="length_ratio"):
        _upper_arm(length_ratio=float("nan"))

def test_rotation_limits_reject_inverted_bounds():
    with pytest.raises(ValueError, match="rotation_limits.x"):
        RotationLimits(x=(90.0, -90.0), y=(-98.0, 180.0), z=(-97.0, 91.0))

def test_rotation_limits_reject_nan_bounds():
    with pytest.raises(ValueError, match="rotation_limits.x"):
        RotationLimits(x=(float("nan"), 90.0), y=(-98.0, 180.0), z=(-97.0, 91.0))

def test_rotation_limits_accept_valid_bounds():
    limits = RotationLimits(x=(-135.0, 90.0), y=(-98.0, 180.0), z=(-97.0, 91.0))
    assert limits.x == (-135.0, 90.0)

def test_name_with_space_is_rejected():
    with pytest.raises(ValueError, match="snake_case"):
        _upper_arm(name="upper arm")

def test_parent_attachment_values_round_trip():
    assert ParentAttachment("origin") is ParentAttachment.ORIGIN
    assert ParentAttachment("distal") is ParentAttachment.DISTAL
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --with pytest pytest skellyforge/tests/test_segment_definition.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'skellyforge.skellymodels.standard_human.segment_definition'`

- [x] **Step 3: Write minimal implementation**

```python
# skellyforge/skellymodels/standard_human/segment_definition.py
"""The authored unit of the standard human: one rigid-body segment.

A segment is an **origin**, an **orientation**, and a **length**. All three are
declared here as named keypoints plus a rest pose, and this one
declaration is evaluated twice — against the T-pose to build the reference
geometry, and against each frame to read the live pose.

Keypoint names are side-agnostic within a part; composition prefixes them.
"""

from __future__ import annotations

import math

from dataclasses import dataclass
from enum import Enum

class ParentAttachment(str, Enum):
    """Which end of the parent this segment's origin sits at."""

    ORIGIN = "origin"
    """Branch from the parent's origin — e.g. both upper legs and the spine
    branch from the hips' origin."""

    DISTAL = "distal"
    """Continue from the parent's distal end — the common case."""

@dataclass(frozen=True)
class RotationLimits:
    """Joint range-of-motion limits in degrees, in the segment's local frame.

    **Declared, not yet enforced** — the solver ignores these in SF-SM. They are
    specified now so the model is complete and the values are reviewed alongside
    the anatomy they constrain, rather than bolted on later.
    """

    x: tuple[float, float]
    y: tuple[float, float]
    z: tuple[float, float]

    def __post_init__(self) -> None:
        for axis in ("x", "y", "z"):
            low, high = getattr(self, axis)
            if not math.isfinite(low) or not math.isfinite(high):
                raise ValueError(
                    f"rotation_limits.{axis} bounds must be finite, got ({low}, {high})"
                )
            if low > high:
                raise ValueError(
                    f"rotation_limits.{axis} lower bound {low} exceeds upper bound {high}"
                )

@dataclass(frozen=True)
class SegmentDefinition:
    """One VRM-1.0-aligned rigid body, authored side-agnostically."""

    name: str
    parent: str | None
    parent_attachment: ParentAttachment
    origin_keypoint: str
    long_axis_keypoint: str
    twist_keypoint: str | None
    rest_rotation: tuple[float, float, float]
    rest_roll: float
    length_ratio: float
    rotation_limits: RotationLimits | None = None

    def __post_init__(self) -> None:
        if not self.name or self.name != self.name.lower() or " " in self.name:
            raise ValueError(f"segment name must be snake_case, got {self.name!r}")

        if self.origin_keypoint == self.long_axis_keypoint:
            raise ValueError(
                f"segment {self.name!r}: origin_keypoint and long_axis_keypoint are both "
                f"{self.origin_keypoint!r}. The segment vector would be zero-length and no "
                f"orientation could be resolved from it."
            )

        if self.twist_keypoint is not None and self.twist_keypoint == self.long_axis_keypoint:
            raise ValueError(
                f"segment {self.name!r}: twist_keypoint is {self.twist_keypoint!r}, the same as "
                f"long_axis_keypoint. A twist reference collinear with the long axis resolves "
                f"nothing."
            )

        if not math.isfinite(self.length_ratio) or self.length_ratio <= 0.0:
            raise ValueError(
                f"segment {self.name!r}: length_ratio must be finite and > 0, got {self.length_ratio}"
            )

    @property
    def resolves_twist(self) -> bool:
        """Whether this segment's roll is determined by its own keypoints.

        ``False`` means the twist falls back to the critically damped minimal-twist
        solve — the tier is a *consequence* of the declaration, not a separate policy.
        """
        return self.twist_keypoint is not None

    def required_keypoints(self) -> set[str]:
        """Every keypoint this segment needs to be solvable."""
        names = {self.origin_keypoint, self.long_axis_keypoint}
        if self.twist_keypoint is not None:
            names.add(self.twist_keypoint)
        return names
```

- [x] **Step 4: Run test to verify it passes**

Run: `uv run --with pytest pytest skellyforge/tests/test_segment_definition.py -v`
Expected: PASS — 13 passed (code review added NaN guards + 6 pinning tests; the full suite is 64 green)

- [ ] **Step 5: Commit** *(the user owns git — report the stopping point and stop)*

---

### Task 2: Part composition — author once, instantiate per side

**Files:**
- Create: `skellyforge/skellymodels/standard_human/segment_parts.py`
- Test: `skellyforge/tests/test_part_composition.py`

- [ ] **Step 1: Write the failing test**

```python
# skellyforge/tests/test_part_composition.py
import math
import pytest
from skellyforge.skellymodels.standard_human.segment_definition import (
    ParentAttachment, SegmentDefinition,
)
from skellyforge.skellymodels.standard_human.segment_parts import SegmentPart, compose_parts

def _hand_part() -> SegmentPart:
    return SegmentPart(
        name="hand",
        segments=(
            SegmentDefinition(
                name="hand", parent="lower_arm", parent_attachment=ParentAttachment.DISTAL,
                origin_keypoint="wrist", long_axis_keypoint="middle_finger_mcp",
                twist_keypoint="thumb_cmc",
                rest_rotation=(0.0, math.radians(90.0), 0.0), rest_roll=math.radians(90.0),
                length_ratio=0.0505,
            ),
            SegmentDefinition(
                name="thumb_metacarpal", parent="hand", parent_attachment=ParentAttachment.ORIGIN,
                origin_keypoint="thumb_cmc", long_axis_keypoint="thumb_mcp", twist_keypoint=None,
                rest_rotation=(0.0, math.radians(90.0), math.radians(-45.0)), rest_roll=0.0,
                length_ratio=0.0194,
            ),
        ),
    )

def test_instantiating_a_part_prefixes_segment_names():
    composed = compose_parts([(_hand_part(), "left_")])
    assert {s.name for s in composed} == {"left_hand", "left_thumb_metacarpal"}

def test_instantiating_a_part_prefixes_keypoint_names():
    composed = compose_parts([(_hand_part(), "left_")])
    hand = next(s for s in composed if s.name == "left_hand")
    assert hand.origin_keypoint == "left_wrist"
    assert hand.long_axis_keypoint == "left_middle_finger_mcp"
    assert hand.twist_keypoint == "left_thumb_cmc"

def test_instantiating_a_part_prefixes_parent_references_within_the_part():
    composed = compose_parts([(_hand_part(), "left_")])
    thumb = next(s for s in composed if s.name == "left_thumb_metacarpal")
    assert thumb.parent == "left_hand"

def test_a_parent_outside_the_part_is_still_prefixed_and_joins_by_name_agreement():
    # `lower_arm` lives in the body part; under prefix `left_` it becomes
    # `left_lower_arm`, which is exactly what the body part produces. Parts join
    # because their names coincide after prefixing — there is no attachment step.
    composed = compose_parts([(_hand_part(), "left_")])
    hand = next(s for s in composed if s.name == "left_hand")
    assert hand.parent == "left_lower_arm"

def test_the_same_part_instantiated_twice_yields_structurally_identical_sets():
    composed = compose_parts([(_hand_part(), "left_"), (_hand_part(), "right_")])
    left = sorted(s.name.removeprefix("left_") for s in composed if s.name.startswith("left_"))
    right = sorted(s.name.removeprefix("right_") for s in composed if s.name.startswith("right_"))
    assert left == right
    assert len(composed) == 4

def test_duplicate_segment_names_after_composition_raise():
    with pytest.raises(ValueError, match="duplicate segment name"):
        compose_parts([(_hand_part(), "left_"), (_hand_part(), "left_")])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --with pytest pytest skellyforge/tests/test_part_composition.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named '...segment_parts'`

- [ ] **Step 3: Write minimal implementation**

```python
# skellyforge/skellymodels/standard_human/segment_parts.py
"""Parts: named, side-agnostic groups of segments, instantiated by prefix.

A hand has 16 segments and a human has two hands. Writing the hand out twice is
duplicated information, so the hand is authored **once** and instantiated with the
prefixes ``left_`` and ``right_``.

Parts join by **name agreement**: the hand's local ``wrist`` becomes ``left_wrist``
under its prefix, which is already the body's wrist keypoint, and its parent
reference ``lower_arm`` becomes ``left_lower_arm``, which is already a body segment.
There is no separate attachment mechanism — once expanded there is nothing left over
to get wrong.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from skellyforge.skellymodels.standard_human.segment_definition import SegmentDefinition

@dataclass(frozen=True)
class SegmentPart:
    """A named group of segments, authored without a side."""

    name: str
    segments: tuple[SegmentDefinition, ...]

def _prefixed(value: str | None, prefix: str) -> str | None:
    return None if value is None else f"{prefix}{value}"

def instantiate_part(part: SegmentPart, prefix: str) -> list[SegmentDefinition]:
    """Expand one part under *prefix*, prefixing names, keypoints and parents."""
    return [
        dataclasses.replace(
            segment,
            name=f"{prefix}{segment.name}",
            parent=_prefixed(segment.parent, prefix),
            origin_keypoint=f"{prefix}{segment.origin_keypoint}",
            long_axis_keypoint=f"{prefix}{segment.long_axis_keypoint}",
            twist_keypoint=_prefixed(segment.twist_keypoint, prefix),
        )
        for segment in part.segments
    ]

def compose_parts(
    parts: Iterable[tuple[SegmentPart, str]],
) -> list[SegmentDefinition]:
    """Expand every (part, prefix) pair into one flat segment list.

    Downstream consumers — the solver, the stream schema — receive a flat indexed
    list exactly as before. They receive it from this build step instead of from a
    file, which is also where the per-frame O(n) lookups stop being O(n^2).
    """
    composed: list[SegmentDefinition] = []
    seen: set[str] = set()
    for part, prefix in parts:
        for segment in instantiate_part(part, prefix):
            if segment.name in seen:
                raise ValueError(
                    f"duplicate segment name {segment.name!r} after composing part "
                    f"{part.name!r} with prefix {prefix!r}"
                )
            seen.add(segment.name)
            composed.append(segment)
    return composed
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --with pytest pytest skellyforge/tests/test_part_composition.py -v`
Expected: PASS — 6 passed

- [ ] **Step 5: Report the stopping point**

---

### Task 3: Author the body part

**Files:**
- Create: `skellyforge/skellymodels/standard_human/body_part.py`
- Test: extend `skellyforge/tests/test_part_composition.py`

The body part is authored **side-agnostically**: `shoulder`, `upper_arm`, `upper_leg` are written once and
instantiated `left_`/`right_`; midline segments (`hips`, `spine`, `chest`, `neck`, `head`) are written in a
midline part with an empty prefix.

Segment table — VRM 1.0 names, keypoint roles derived from the Blender rig's constraint targets:

| segment | parent | attach | origin kp | long-axis kp | twist kp |
|---|---|---|---|---|---|
| `hips` | — | — | `hips_center` | `trunk_center` | `right_hip` |
| `spine` | `hips` | origin | `hips_center` | `trunk_center` | `right_hip` |
| `chest` | `spine` | distal | `trunk_center` | `neck_center` | `right_shoulder` |
| `upper_chest` | `chest` | distal | `mid_sternum` | `neck_center` | `right_shoulder` |
| `neck` | `upper_chest` | distal | `neck_center` | `head_center` | `nose` |
| `head` | `neck` | distal | `head_center` | `head_vertex` | `nose` |
| `shoulder` | `upper_chest` | distal | `sternoclavicular` | `shoulder` | `neck_center` |
| `upper_arm` | `shoulder` | distal | `shoulder` | `elbow` | `wrist` |
| `lower_arm` | `upper_arm` | distal | `elbow` | `wrist` | `middle_finger_mcp` |
| `upper_leg` | `hips` | origin | `hip` | `knee` | `ankle` |
| `lower_leg` | `upper_leg` | distal | `knee` | `ankle` | `big_toe` |
| `foot` | `lower_leg` | distal | `ankle` | `foot_ball` | `heel` |
| `toes` | `foot` | distal | `foot_ball` | `big_toe` | `small_toe` |

Three keypoints are **derived** and are new work in the tracker mappings (Task 6): `mid_sternum`,
`head_vertex`, `foot_ball`. Rest rotations and rolls port from the addon's `freemocap_tpose` — **with a
name translation, not a copy**: the addon keys are MediaPipe-style (`pelvis` → `hips`, `thigh` →
`upper_leg`, `shin` → `lower_leg`, `forearm` → `lower_arm`, `face` → `head`, `spine.001` → `chest`);
`upper_chest` and `toes` have no addon counterpart and are authored from the VRM hierarchy with the
nearest addon rotation or rest-identity, stating provenance per §7. ROM limits port from the addon's
`LimitRotationConstraint` values; segments the addon gives no limit (`hips`, `head`, `upper_chest`,
`shoulder`, `toes`) get `rotation_limits=None` — an unbacked number violates the provenance rule, and
limits are declared-not-enforced this workstream anyway.

- [ ] **Step 1:** Write `test_body_part_every_segment_reaches_the_root` — walk `parent` from each segment
      and assert termination at `hips` with no cycle.
- [ ] **Step 2:** Write `test_body_part_declares_no_unreachable_keypoint` — assert
      `required_keypoints()` over the composed body equals the documented body keypoint set.
- [ ] **Step 3:** Run both; expected FAIL (`body_part` does not exist).
- [ ] **Step 4:** Author `body_part.py` per the table above.
- [ ] **Step 5:** Run; expected PASS.
- [ ] **Step 6:** Report the stopping point.

---

### Task 4: Author the hand part and the face part; rewrite `StandardHuman`

**Files:**
- Create: `skellyforge/skellymodels/standard_human/hand_part.py`, `face_part.py`
- Modify: `skellyforge/skellymodels/standard_human/standard_human_model.py` **[rewrite]**
- Test: extend `skellyforge/tests/test_part_composition.py`

The hand is 16 segments over the 21 named hand keypoints, authored once:

```
wrist → thumb_cmc → thumb_mcp → thumb_ip → thumb_tip
            └ thumb_metacarpal ┘└ thumb_proximal ┘└ thumb_distal ┘

wrist → {index,middle,ring,little}_finger_mcp → pip → dip → tip
                       └ {f}_proximal ┘└ {f}_intermediate ┘└ {f}_distal ┘

hand: origin=wrist, long_axis=middle_finger_mcp, twist=thumb_cmc
```

`wrist → *_mcp` is the metacarpal/carpal span; VRM does not model it as a bone, so it is absorbed into
`hand`. VRM names `little`, the keypoints name `pinky` — the segment is `little_*`, the keypoint stays
`pinky_*`, and the declaration is where they meet.

The face part declares `left_eye`, `right_eye`, `jaw` (present, undriven per locked decision 4) and the 52
ARKit blendshape channels. Per SF-AL A4 the face is **not** a segment chain: blendshapes compose alongside
the skeleton rather than being forced into a shared abstraction.

- [ ] **Step 1:** Write `test_hand_part_has_sixteen_segments` and
      `test_hand_composes_onto_the_body_by_name_agreement` (assert `left_hand.parent == "left_lower_arm"`
      and that `left_lower_arm` exists in the composed body).
- [ ] **Step 2:** Run; expected FAIL.
- [ ] **Step 3:** Author `hand_part.py` and `face_part.py`.
- [ ] **Step 4:** Run; expected PASS. Assert the composed human is **55 segments**, matching `BONE_ALIASES`.
- [ ] **Step 5:** Rewrite `StandardHuman` onto composition: it holds the part list, calls `compose_parts()`
      once at load, and exposes the flat indexed segment list plus **`dict`-backed** name→segment and
      parent→children indices built once. This is where D13's O(n²) per-frame scans stop being O(n²)
      (`get_children()` / `_get_bone_by_name()` are linear scans inside the per-segment loop today —
      2.07 ms/frame at 21 segments, extrapolating to ~14 ms at 55). Per SF-AL A5, `StandardHuman` describes
      **one** human; multi-subject is a list of them and the model grows no subject dimension. Per A7,
      composition replaces the `Actor → Human/Animal/Board` inheritance.
- [ ] **Step 6:** Write `test_hierarchy_accessors_agree` — `segment_parents`, children, and root-to-segment
      chains describe the same tree ([`14`](../14-engine-testing-strategy.md) §7).
- [ ] **Step 7:** Run; expected PASS. Report the stopping point.

---

### Task 5: Reference geometry from the T-pose

**Files:**
- Create: `skellyforge/skellymodels/standard_human/reference_geometry.py`
- Test: `skellyforge/tests/test_reference_geometry.py`

Ports `add_rig_by_bone`'s construction: root height from measured leg segments, then each segment's origin
from its parent per `parent_attachment`, its vector as `rest_rotation @ [0, 0, length]`, and its rest twist
from `rest_roll`.

- [ ] **Step 1:** Write `test_reference_basis_is_right_handed` — assert `det(basis) == +1` for **every**
      segment on **both** sides (SF-AL A3's guard; a left-handed frame is still orthonormal so nothing
      else would catch it).
- [ ] **Step 2:** Write `test_reference_geometry_scales_linearly_with_measured_lengths` — double every
      measured length, assert every origin doubles.
- [ ] **Step 3:** Write `test_no_segment_has_zero_length_in_the_reference_pose`.
- [ ] **Step 4:** Run; expected FAIL.
- [ ] **Step 5:** Implement `build_reference_geometry(segments, measured_lengths)` returning
      `dict[str, SegmentReferenceGeometry]` where the geometry carries `origin`, `basis` (3×3) and `length`
      — **not** a distal point.
- [ ] **Step 6:** Run; expected PASS.
- [ ] **Step 7:** Report the stopping point.

---

### Task 6: The required-keypoint contract, per tracker

**Files:**
- Modify: `skellytracker/core/io/tracker_mapping.py`
- Modify: the four `*_to_canonical_mapping.yaml` files
- Rename: the four mapping YAMLs + the four detector `mapping_yaml_path()` references to
  `{tracker}_keypoint_mapping.yaml` — the `to_canonical` filename asserts the retired layer (§3)
- Test: `skellytracker/tests/test_mapping_completeness.py` (new file — `skellytracker/tests/` exists with detector tests + conftest)

- [ ] **Step 1:** Write `test_every_tracker_mapping_produces_the_full_required_keypoint_set` —
      parametrized over all four mapping YAMLs, asserting each produces every name in the model's
      `required_keypoints()`.
- [ ] **Step 2:** Write `test_a_mapping_referencing_an_unproduced_keypoint_raises_at_load` — the
      fail-loud half of D24. A keypoint missing *this frame* is occlusion and is still skipped silently.
- [ ] **Step 3:** Run; expected FAIL — `mid_sternum`, `head_vertex`, `foot_ball` are produced by no mapping.
- [ ] **Step 4:** Add `anatomical_offset` definitions for the three derived keypoints to **both** body
      mappings, identically (D7: every tracker produces the full set, or the segment model means
      different things depending on which detector ran).
- [ ] **Step 5:** Rename the four mapping YAMLs to `{tracker}_keypoint_mapping.yaml`; update the four
      detector `mapping_yaml_path()` references and the `tracker_mapping.py` docstring.
- [ ] **Step 6:** Run; expected PASS.
- [ ] **Step 7:** Report the stopping point — **this ends in skellytracker and skellyforge, so nothing
      reaches FreeMoCap until the user commits + pushes, then `uv lock --upgrade-package` + `uv sync`.**

---

### Task 7: Solver reads declared keypoints

**Files:**
- Modify: `skellyforge/kinematics/orientation_solver.py`
- Test: `skellyforge/tests/test_solver_keypoint_declared.py`

- [ ] **Step 1:** Write `test_every_declared_segment_produces_an_orientation` — feed a full plausible
      keypoint set, assert **55** world quaternions. Today's solver returns 16 of 21 because
      `_get_distal_position` needs a child, so `head`, both hands and both toes silently produce nothing.
- [ ] **Step 2:** Write `test_a_segment_with_multiple_children_uses_its_declared_long_axis_keypoint` —
      today `hips`' distal is whichever child is declared first, so a reordering silently redirects it.
- [ ] **Step 3:** Write `test_leaf_segments_are_solvable` — `head`, `left_hand`, `left_toes`.
- [ ] **Step 4:** Write `test_coincident_origin_and_long_axis_keypoints_raise_at_model_load_not_at_solve`
      — the `neck` crash becomes a load-time validation failure (Task 1) instead of a per-frame exception
      that kills the aggregator node.
- [ ] **Step 5:** Run; expected FAIL.
- [ ] **Step 6:** Replace `live_joint_positions: dict[segment_name, position]` with
      `keypoints: dict[keypoint_name, position]`; resolve origin/long-axis/twist per the declaration;
      delete `_get_distal_position`.
- [ ] **Step 7:** Run; expected PASS. Then run the **whole** suite —
      `uv run --with pytest pytest skellyforge/tests/ -q` — expected 51 existing + new, all green.
- [ ] **Step 8:** Report the stopping point.

---

### Task 8: One length estimator, two windows

**Files:**
- Modify: `skellyforge/kinematics/online_segment_lengths.py`
- Delete: `freemocap/core/tasks/mocap/rigid_body/online_segment_lengths.py`
- Modify: `freemocap/tests/rigid_body/test_rolling_bone_lengths.py` (repoint the import)
- Test: `skellyforge/tests/test_segment_length_estimator.py`

Realtime and posthoc run the **same** estimator — per-segment median of the origin→long-axis distance,
NaN-excluded. The only difference is the window: a rolling duration for streaming, the whole recording for
posthoc. Posthoc is not degraded to match realtime; it passes an unbounded window.

The FreeMoCap copy is a **whitespace-and-docstring-only** duplicate, and `skeleton_rigidifier.py:44`
already imports the SkellyForge one — only the FreeMoCap test still imports the copy.

- [ ] **Step 1:** Write `test_unbounded_window_reproduces_the_batch_median` — feed a synthetic recording,
      assert the estimator's result equals `statistics.median` over all frames.
- [ ] **Step 2:** Write `test_rolling_window_drops_samples_older_than_the_window`.
- [ ] **Step 3:** Write `test_a_segment_with_no_samples_falls_back_to_its_anthropometric_seed`.
- [ ] **Step 4:** Run; expected FAIL.
- [ ] **Step 5:** Parameterize the window (`window_seconds: float | None`, `None` = unbounded); key by
      **segment name**, not `"parent->child"` — the arrow key and both `split("->")` sites (F2) disappear
      because length is a property of a segment.
- [ ] **Step 6:** Run; expected PASS. Delete the FreeMoCap copy and repoint its test. The deletion is a
      **freemocap working-tree** change — freemocap's env reads its own tree, so it takes effect locally
      immediately; it does not need a push. The skellyforge estimator itself still reaches freemocap only
      at the commit round, like every skellyforge change.
- [ ] **Step 7:** Report the stopping point.

---

### Task 9: Retire the old models

**Files:**
- Modify: `freemocap/core/pipeline/realtime/realtime_aggregator_node.py:876-1029`
- Delete: `skellyforge/biomechanics/`, `skellyforge/pipelines/dlc_pipeline.py`
- Modify: `skellyforge/skellymodels/tracker_info/canonical_body.yaml`, `canonical_hand.yaml`

- [ ] **Step 1:** Delete `_BONE_TO_LANDMARK`, `_standard_human_cache`, `_get_standard_human()`,
      `_build_solver_positions()`; the aggregator loads the composed `StandardHuman` from SkellyForge and
      passes keypoints straight through. Closes D11, D12, D16's remainder.
- [ ] **Step 2:** Delete `skellyforge/biomechanics/` (F5) and `dlc_pipeline.py`.
- [ ] **Step 3:** Re-express CoM against segments using **de Leva (1996)** — mass fraction and
      CoM-as-fraction-of-segment-length, referenced to **joint centres**, which is what our origins are.
      Winter's table references bony landmarks, which is why `canonical_body.yaml` needed a `head` segment
      spanning ear-to-ear. Citation:
      de Leva, P. (1996). *Adjustments to Zatsiorsky-Seluyanov's segment inertia parameters.*
      Journal of Biomechanics, 29(9), 1223–1230.
- [ ] **Step 4:** Strip `canonical_body.yaml` / `canonical_hand.yaml` to the **keypoint list**
      only; `segment_connections`, `joint_hierarchy` and `bone_length_ratios` are superseded by the segment
      model. Repoint `tracker_schema_message.py`'s render connections at the composed segments.
- [ ] **Step 5:** Run every suite in both repos; report.

---

### Task 10: Rewrite the docs the old framing infected

- [ ] **Step 1:** Rewrite [`13`](../13-tracker-to-canonical-mapping.md) as the keypoint → segment
      reference-geometry boundary, and re-declare it SSOT for the surviving vocabulary
      (**keypoint** / **segment**; *landmark* retired).
- [ ] **Step 2:** [`00`](../00-overview.md) § Glossary — the four-load-bearing-terms table.
- [ ] **Step 3:** [`01`](../01-canonical-data-model.md) § what the frame carries — the landmark row.
- [ ] **Step 4:** [`12`](../12-standard-human-model.md) — § *Marker → bone retarget* becomes *what defines
      a segment's reference geometry*; revise the SC joint to **bilateral** (the open D7/D8 item).
- [ ] **Step 5:** [`07`](07-spec-reconciliation.md) §1 — record that the terminology pass installed a
      layer that is now retired, and why. **Do not delete the section**; supersession is recorded, not
      rewritten.
- [ ] **Step 6:** [`08`](08-skellyforge-alignment.md) — F1/F2/F3 and checklist items 3–6 are replaced by
      this plan, not edited. A1–A7 survive.
- [ ] **Step 7:** [`04`](04-ui-wedge.md) — its `ChannelKind` is the new six-group version but its "Sample
      decode flow" (lines 227–236) still describes the old five-group order **and** the old rotation
      ordering; its "dual-protocol coexistence" note contradicts D36. Neither is in the defect register.
- [ ] **Step 8:** [`IMPLEMENTATION_PLAN`](../IMPLEMENTATION_PLAN.md) — progress log entry + scope.

---

## 6. Definition of done

- One segment model. `canonical_body.yaml`'s segment/hierarchy/ratio stack, `_BONE_TO_LANDMARK`,
  `HumanBone.proximal_landmark` and the aggregator bootstrap are gone.
- The composed standard human is **55 segments** — body, hands, face — matching `BONE_ALIASES`.
- **Every** segment produces an orientation. No silent skips, no first-child inference.
- Every tracker mapping produces the full required keypoint set; a gap fails at load.
- Realtime and posthoc share one length estimator; posthoc passes an unbounded window.
- ROM limits are declared on every major segment (not yet enforced).
- No test passes under both operand orders, both handedness conventions, or both component orders
  ([`14`](../14-engine-testing-strategy.md)).

## 7. Open items

- ~~**`mid_sternum`, `head_vertex`, `foot_ball` offset magnitudes** need a citable source.~~
  **Resolved 2026-08-12 — our own best estimates are acceptable** where standard anthropometry tables don't
  define the point. Winter and Drillis & Contini tabulate segment *lengths*, not off-surface joint-centre
  placement, so for several of these no published value exists to find.

  Two rules hold regardless of source, and they are what keep the estimate honest:

  1. **Every offset is a ratio of a named `reference_length`, never an absolute distance.** A millimetre
     constant silently assumes one body size; a ratio scales with the subject. This is non-negotiable and
     is independent of where the number came from.
  2. **Each value states its provenance in a comment** — sourced (with the citation) or estimated (saying
     so, and from what). The existing SC offset is the model to follow: *"Estimated from surface anatomy
     rather than taken from a published table — Winter and Drillis & Contini tabulate segment lengths, not
     SC joint placement. Refine if a sourced value appears."*

  A best estimate that says it is one is a known quantity. An unlabelled number is indistinguishable from a
  measured one, and that is the failure mode — not the estimate itself.
- **Twist-resolution best practices.** The two-tier design (§1) — declared twist keypoint where one
  exists, damped minimal roll where it does not — follows the Blender addon's constraint model and the
  proven D3/D4 damping code, but "minimize roll when unspecified" deserves a check against
  reconstruction-kinematics best practice before Task 7 locks the solver in. Trigger: before Task 7's
  solver rewrite; do not hold Tasks 1–6 on it. Sources: humanoid-IK / marker-set-reconstruction literature
  on twist (roll) resolution for under-constrained segments; the addon's own behaviour (DampedTrack leaves
  roll free unless a LockedTrack removes it) is the working reference.
- **ROM enforcement.** Blender resolves limits by iterating constraints; a closed-form clamp on a
  quaternion solve is not equivalent. Needs its own design once the model lands.
- **`.VRM` export.** Needs the skeleton (this plan), the alias table (exists), and a **skinned mesh** —
  the addon's `skelly_bones.py` maps mesh pieces to bone groups with a nominal `mesh_length` to scale
  against measured lengths. Its own plan, after this one.
