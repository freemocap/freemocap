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
The two-tier design is scheduled for a check against reconstruction-kinematics best practice before
Phase F (see [§7](#7-open-items)) — it follows the addon's constraint model and the proven D3/D4
damping, so the check is confirmation, not a blocker.

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
5. **Full VRM 1.0 humanoid: 55 segments — plus 5 FreeMoCap face-detail segments (60 total).** Body +
   hands + face. Not a subset. Parts authored once,
   instantiated per side. (The face-detail five — nose, ears, mouth corners — are tracked-keypoint head
   axes beyond VRM's humanoid set; added 2026-08-13, see the face-part section below.)
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
 tracker keypoints ──[ {tracker}_to_standard_human_mapping.yaml ]──▶ named keypoints
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
the retired "canonical" vocabulary — `{tracker}_to_standard_human_mapping.yaml` (executed 2026-08-13, Task 6).

## 4. File structure

**Create — `skellyforge/skellymodels/standard_human/`:**

| File | Responsibility |
|---|---|
| `segment_definition.py` | `SegmentDefinition`, `RotationLimits`, `ParentAttachment` — the authored unit |
| `segment_parts.py` | `SegmentPart` (a named, side-agnostic set of segments) + `compose_parts()` |
| `body_part.py` | the body part: 20 segments (6 midline + 7×2 limbs), authored once |
| `hand_part.py` | the hand part: 16 segments, authored once, instantiated twice |
| `face_part.py` | eyes + jaw segments (driven, VRM 1.0 face bones) + the 52 blendshape channels |
| `standard_human_model.py` | **[rewrite]** `StandardHuman` — composed parts → flat indexed segment list |
| `dead_reference_geometry.py` | `SegmentReferenceGeometry` (origin + basis + length) + `build_reference_geometry()` |

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

- [x] **Step 1: Write the failing test**

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

def test_empty_prefix_leaves_midline_part_names_unchanged():
    # Task 3 authors the body's midline segments (hips, spine, chest, neck, head)
    # under an empty prefix — names and parents must come through untouched.
    composed = compose_parts([(_hand_part(), "")])
    assert {s.name for s in composed} == {"hand", "thumb_metacarpal"}
    hand = next(s for s in composed if s.name == "hand")
    assert hand.parent == "lower_arm"
    assert hand.origin_keypoint == "wrist"

def test_root_parent_none_survives_prefixing():
    root = SegmentDefinition(
        name="hips", parent=None, parent_attachment=ParentAttachment.ORIGIN,
        origin_keypoint="hips_center", long_axis_keypoint="trunk_center",
        twist_keypoint="right_hip",
        rest_rotation=(0.0, 0.0, 0.0), rest_roll=0.0, length_ratio=0.145,
    )
    part = SegmentPart(name="midline", segments=(root,))
    composed = compose_parts([(part, "")])
    assert composed[0].parent is None
    # and a root authored inside a prefixed part would stay None too
    composed_prefixed = compose_parts([(part, "left_")])
    assert composed_prefixed[0].parent is None

def test_required_keypoints_are_fully_prefixed_after_composition():
    # The tracker-mapping boundary contract (Task 6) keys on these names —
    # a missed prefix here would silently break the model's required-keypoint set.
    composed = compose_parts([(_hand_part(), "left_")])
    hand = next(s for s in composed if s.name == "left_hand")
    thumb = next(s for s in composed if s.name == "left_thumb_metacarpal")
    assert hand.required_keypoints() == {"left_wrist", "left_middle_finger_mcp", "left_thumb_cmc"}
    assert thumb.required_keypoints() == {"left_thumb_cmc", "left_thumb_mcp"}

def test_midline_references_fall_back_to_unprefixed_names():
    # The limb part's shoulder attaches to the midline `upper_chest` and its twist
    # references the midline `neck_center`; the leg attaches to the midline `hips`.
    # Under prefix `left_` those become `left_upper_chest` / `left_neck_center` /
    # `left_hips`, none of which exist — name agreement resolves them back.
    midline = SegmentPart(name="midline", segments=(
        SegmentDefinition(
            name="hips", parent=None, parent_attachment=ParentAttachment.ORIGIN,
            origin_keypoint="hips_center", long_axis_keypoint="trunk_center",
            twist_keypoint="right_hip",
            rest_rotation=(0.0, 0.0, 0.0), rest_roll=0.0, length_ratio=0.145,
        ),
        SegmentDefinition(
            name="upper_chest", parent="hips", parent_attachment=ParentAttachment.DISTAL,
            origin_keypoint="mid_sternum", long_axis_keypoint="neck_center",
            twist_keypoint="right_shoulder",
            rest_rotation=(0.0, 0.0, 0.0), rest_roll=0.0, length_ratio=0.055,
        ),
    ))
    limb = SegmentPart(name="limb", segments=(
        SegmentDefinition(
            name="shoulder", parent="upper_chest", parent_attachment=ParentAttachment.DISTAL,
            origin_keypoint="sternoclavicular", long_axis_keypoint="shoulder",
            twist_keypoint="neck_center",
            rest_rotation=(-math.pi / 2, 0.0, 0.0), rest_roll=0.0, length_ratio=0.103,
        ),
        SegmentDefinition(
            name="upper_leg", parent="hips", parent_attachment=ParentAttachment.ORIGIN,
            origin_keypoint="hip", long_axis_keypoint="knee", twist_keypoint="ankle",
            rest_rotation=(math.pi, 0.0, 0.0), rest_roll=0.0, length_ratio=0.245,
        ),
    ))
    composed = compose_parts([(midline, ""), (limb, "left_")])
    shoulder = next(s for s in composed if s.name == "left_shoulder")
    upper_leg = next(s for s in composed if s.name == "left_upper_leg")
    assert shoulder.parent == "upper_chest"
    assert shoulder.twist_keypoint == "neck_center"
    assert upper_leg.parent == "hips"
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --with pytest pytest skellyforge/tests/test_part_composition.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named '...segment_parts'`

- [x] **Step 3: Write minimal implementation**

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
from collections.abc import Iterable
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

    References resolve by **name agreement**, parents and keypoints alike. A
    prefixed reference that does not exist falls back to its unprefixed name when
    that name is declared (a midline segment or keypoint): ``left_shoulder`` finds
    the midline ``upper_chest``, its twist reference finds ``neck_center``. A
    reference whose fallback resolves to nothing is kept as authored — the
    composed model's validators (Task 4) raise on unresolvable parents.
    """
    midline_keypoints: set[str] = set()
    for part, prefix in parts:
        if prefix == "":
            for segment in part.segments:
                midline_keypoints |= segment.required_keypoints()

    composed: list[SegmentDefinition] = []
    seen: set[str] = set()
    for part, prefix in parts:
        for segment in instantiate_part(part, prefix):
            if segment.name in seen:
                raise ValueError(
                    f"duplicate segment name {segment.name!r} after composing part "
                    f"{part.name!r} with prefix {prefix!r}"
                )
            if prefix:
                segment = _resolve_midline_references(segment, midline_keypoints)
            seen.add(segment.name)
            composed.append(segment)

    resolved: list[SegmentDefinition] = []
    for segment in composed:
        parent = segment.parent
        if parent is not None and parent not in seen:
            unprefixed = parent.split("_", 1)[1] if "_" in parent else parent
            if unprefixed in seen:
                parent = unprefixed
        resolved.append(dataclasses.replace(segment, parent=parent))
    return resolved


def _resolve_midline_references(
    segment: SegmentDefinition,
    midline_keypoints: set[str],
) -> SegmentDefinition:
    """Fall prefixed keypoint references back to midline names where they exist.

    ``left_neck_center`` does not exist — ``neck_center`` does. References that do
    not name a midline keypoint (``left_elbow``) are left prefixed.
    """
    def resolved(name: str | None) -> str | None:
        if name is None:
            return None
        if name in midline_keypoints:
            return name
        unprefixed = name.split("_", 1)[1] if "_" in name else name
        return unprefixed if unprefixed in midline_keypoints else name

    return dataclasses.replace(
        segment,
        origin_keypoint=resolved(segment.origin_keypoint),
        long_axis_keypoint=resolved(segment.long_axis_keypoint),
        twist_keypoint=resolved(segment.twist_keypoint),
    )
```

- [x] **Step 4: Run test to verify it passes**

Run: `uv run --with pytest pytest skellyforge/tests/test_part_composition.py -v`
Expected: PASS — 10 passed (code review added 3 contract-pinning tests; Task 3 authoring added the midline-fallback test; the full suite is 74 green)

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
`head_vertex`, `foot_ball`.

**Structure:** two parts — `BODY_MIDLINE_PART` (`hips`→`head`, composed under the empty prefix) and
`BODY_LIMB_PART` (shoulder/arm chain + leg chain, authored once, instantiated `left_`/`right_`).
Cross-part references follow the Task 2 name-agreement fallback: `shoulder.parent` → `upper_chest`,
`shoulder.twist` → `neck_center`, `upper_leg.parent` → `hips` — all midline, so the prefixed form
falls back. `hips` and `spine` deliberately span the same endpoints (`hips_center`→`trunk_center`) at
the same ratio — the trunk piece expressed at two VRM levels.

**Twist at the rest pose (recorded intent, code-review finding):** the chain-resolved twist keypoints
(`wrist`, `middle_finger_mcp`, `ankle`) sit on or within a few mm of their segments' long axes in the
T-pose — the rest pose **is** the degenerate case, by design: straight limbs are exactly where the
singularity gate (Task 7) degrades twist to damped-minimal. `resolves_twist` means "a twist keypoint is
declared", not "twist is resolvable at every pose". Task 5's rest approximate axis for these segments
must therefore be a **non-collinear** direction — the elbow/knee hinge axis at rest — never the twist
keypoint itself.

**Authored values (2026-08-12, provenance per §7):**

- **`rest_rotation`** — derived from the canonical T-pose geometry, **not ported from the addon**. The
  addon's `freemocap_tpose` eulers (`pelvis` (−90°,0,0), `thigh` (1°,180°,0), `face` (110°,0,0)) are
  expressed in its Blender bone-space convention and a direct copy would bake that convention in. The
  canonical T-pose is axis-aligned by construction (+Z up, +X forward, +Y = subject's left, arms out
  along ±Y, feet forward), so each rest long-axis is single-axis — and every Euler convention agrees on
  single-axis values: midline chain **+Z** → `(0, 0, 0)`; `shoulder`/`upper_arm`/`lower_arm` **+Y**
  (authored left side) → `(−π/2, 0, 0)`; `upper_leg`/`lower_leg` **−Z** → `(π, 0, 0)`;
  `foot`/`toes` **+X** → `(0, π/2, 0)`. The addon's ±90° side pattern cross-checks the arms.
  **The authored values are the left side's; the right side mirrors by negating Y at reference-geometry
  build** (Task 5, per SF-AL A3: reflect positions, rebuild frames, never reflect a basis).
- **`rest_roll`** — `0.0` everywhere for now. The addon's ±90 rolls (`upper_arm`/`forearm`/`hand`) are
  bone-space artifacts of its armature convention; twist in SF-SM is keypoint-driven, and the rest
  approximate axis is pinned when Task 5 defines the reference basis. A value whose semantics are not
  yet pinned would be silent data corruption.
- **`length_ratio`** — Winter (2009) / Drillis & Contini (1966), the `_BONE_LENGTH_RATIOS` table:
  `hips`/`spine` 0.145 (same span, `hips_to_spine`), `chest` 0.100, `upper_chest` 0.055, `neck` 0.090,
  `head` 0.040, `upper_arm` 0.186, `lower_arm` 0.146, `upper_leg` 0.245, `lower_leg` 0.246.
  **Estimated** (stated in comments): `shoulder` 0.103 (half-biacromial 0.117 minus the SC offset's
  lateral component 0.06·W); `foot` 0.026 / `toes` 0.013 (2:1 split of Winter's 0.039 ankle→toe at the
  metatarsophalangeal joint).
- **`rotation_limits`** — `None` for all segments for now. The addon's `LimitRotationConstraint` values
  are LOCAL euler limits in its bone space (long axis = local +Y); SF-SM's `RotationLimits` live in the
  segment's local frame, whose convention Task 5 pins. Porting before the frame is pinned would land
  silently-wrong numbers — and nothing enforces limits this workstream, so nothing would catch them.
  The declaration mechanism exists (Task 1); values land in the Task 5 pass, when the addon's
  per-bone table is available to translate.

- [x] **Step 1:** Write `test_body_part_every_segment_reaches_the_root` — assert the exact 20-entry
      parent map, then walk `parent` from each segment and assert termination at `hips` with no cycle.
- [x] **Step 2:** Write `test_body_part_declares_exactly_the_documented_keypoint_set` — assert
      `required_keypoints()` over the composed body equals the documented body keypoint set (a
      hand-written 33-name literal: the independent authority Task 6's completeness contract checks
      against — deriving it from the body would make the test tautological).
- [x] **Step 3:** Run both; expected FAIL (`body_part` does not exist).
- [x] **Step 4:** Author `body_part.py` per the table above.
- [x] **Step 5:** Run; expected PASS.
- [ ] **Step 6:** Report the stopping point.

---

### Task 4: Author the hand part and the face part; rewrite `StandardHuman`

**Files:**
- Create: `skellyforge/skellymodels/standard_human/hand_part.py`, `face_part.py`
- Modify: `skellyforge/skellymodels/standard_human/standard_human_model.py` **[rewrite]**
- Test: extend `skellyforge/tests/test_part_composition.py`; new `skellyforge/tests/test_standard_human_model.py`

> **Execution unit (code-review finding, recorded):** the `StandardHuman` rewrite breaks the orientation
> solver — its only skellyforge consumer — and the two solver test files. **Tasks 4–7 therefore land as
> one unit**: the hand/face parts are additive (suite stays green), then the model rewrite + Task 5
> (reference geometry) + Task 7 (solver) execute back-to-back and the suite is green only at the unit's
> end, when the old solver tests are replaced by the Task 7 suite.

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

**Hand authoring (provenance per §7):**

- Keypoint roles per the diagram; every finger segment has `twist_keypoint=None` (fingers fall to the
  damped minimal-roll tier — the addon gives them no LockedTrack either).
- Parents: `hand.parent = lower_arm` (joins the body by name agreement); the finger chains attach to
  `hand` with `parent_attachment=ORIGIN` (the addon's palm metacarpals attach at the parent's head);
  within a chain the attachment is `DISTAL`.
- `rest_rotation` — the T-pose hand points **+X**, fingers fanned in the horizontal plane, authored for
  the **left** hand (the right side mirrors at Task 5): `hand` `(0, π/2, 0)`; per-finger fan angles
  about Z: `thumb` −45°, `index` −17°, `middle` 0° (the reference — the addon's 5.5° middle offset is
  absorbed by its hand-bone axis), `ring` +7.3°, `little` +19°, applied to the metacarpals and every
  bone distal to them. *Sourced: fan magnitudes from the addon's `freemocap_tpose` (45/17/5.5/7.3/19);
  signs from canonical geometry — the authored-left thumb points toward the body midline (−Y). Refine
  if a sourced hand model appears.*
- `length_ratio` (`_BONE_LENGTH_RATIOS`, Buryanov & Kotiuk 2010 via that table): `hand` 0.050
  (wrist→MCP span), thumb `metacarpal` 0.015 / `proximal` 0.018 / `distal` 0.017, finger `proximal`
  0.028 / `intermediate` 0.018 / `distal` 0.014 (all four fingers).
- `rest_roll` 0.0 and `rotation_limits` `None` — same rationale as Task 3 (Task 5 pins the frame).

**Face part:** the three VRM 1.0 face bones — `left_eye`, `right_eye`, `jaw` — declared and **driven**
per the confirmed VRM 1.0 spec (humanoid.md: eyes/jaw are defined bones parented to `head`, "the model's
eye movement controlled by bones"; the 52-channel blendshape side composes alongside, values null until
face tracking — locked decision 4 holds for the *channels*). Declarations: `parent=head`, attach
**ORIGIN** (the face bones branch from the head's origin — the head-center line; DISTAL would place them
at the head vertex); `left_eye`/`right_eye` origin `left_eye`/`right_eye` with long-axis `nose` (the body
mappings produce both); `jaw` origin `jaw` with long-axis `nose` — `jaw` is a **derived keypoint**
(Task 6, `anatomical_offset` from `nose` in the head frame, §7 provenance). Rest geometry follows the
declared axes (2026-08-13, stated): `rest_rotation` for the eyes `(0, π/2, 0)` — the eye→nose axis is
anterior (+X) at the T-pose; for the jaw `(0, asin(0.2/√(0.2²+0.9²)), 0)` ≈ 12.5° — derived from the
Task 6 jaw-offset design (nose→jaw ≈ 0.9·eye-width down, 0.2·eye-width posterior, so jaw→nose ≈
(0.217, 0, 0.976)). Roll 0, twist None (damped minimal roll), `length_ratio` 0.01 nominal (the declared
face spans are ~tens of mm and are never measured; the value only satisfies the `> 0` validation).
The 52 blendshape channels come from the existing `human_blendshapes.get_blendshape_names()`. Per
SF-AL A4 the face is **not** a segment chain: blendshapes compose alongside the skeleton. **The shared
`nose` long-axis keypoint is off-chain** (no authoritative rest position): the reference build does not
emit it in the rest-keypoint map; the solver's per-frame input supplies it live (the body mappings
produce it), and test fixtures supply a schematic position. The face bones therefore skip at the strict
T-pose identity check and solve from live data — geometry now, gaze fidelity with face tracking.

**Face-detail segments (added 2026-08-13, the user's decision):** five more face segments give the
head's tracked-keypoint axes — `nose` (origin `head_center`, long-axis `nose`, rest `(0, π/2, 0)` — +X
forward, the user's specified alignment), `left_ear`/`right_ear` (origin `head_center`, long-axis the
ear keypoint, rest `(−π/2, 0, 0)` — +Y leftward per the user, mirrored for the right), and
`left_mouth`/`right_mouth` (origin the mouth-corner keypoint, long-axis `nose`, rest `(±α, β, 0)` with
`β = asin(0.2/√(0.2²+0.3²+0.35²))`, `α = asin(0.3/(√(0.2²+0.3²+0.35²)·cos β))` — the corner→nose
direction from the SAME ratios as the mapping's derived-corner offsets, the facial-proportions canon
estimate). All five: `parent=head`, ORIGIN, no twist, roll 0, `length_ratio` 0.01 nominal, ROM `None`.
The right-side rest rotations are authored SIDE-AGNOSTICALLY (identical to the left) — the reference
geometry's blanket right-side mirror derives them, exactly like `left_eye`/`right_eye`. Mouth corners:
MediaPipe tracks them (mapped 1:1); RTMPose derives them (Task 6 `anatomical_offset`, lateral
∓0.3·eye-width). The model is **60 segments**, `required_keypoints()` = **76**; the 52 blendshape
channels stay declared-but-null.

**`StandardHuman` rewrite (step 5):** a **frozen dataclass** (validators in `__post_init__`, matching
`SegmentDefinition`; Pydantic leaves the model layer — segments carry no numpy arrays so nothing needs
`arbitrary_types_allowed`):

- Fields: `name: str`, `parts: tuple[tuple[SegmentPart, str], ...]`, `segments: list[SegmentDefinition]`
  (composed flat, authoring order), `blendshape_channels: list[str]` (the 52).
- Built **once at load**: `_segment_by_name: dict[str, SegmentDefinition]` and
  `_children_by_parent: dict[str, list[SegmentDefinition]]` — D13's O(n²) per-frame scans die here
  (`get_children()` / `_get_bone_by_name()` were linear scans inside the per-segment loop: 2.07 ms/frame
  at 21 segments, ~14 ms extrapolated at 55).
- Accessors: `segment_names`, `segment_parents: dict[str, str | None]`, `joint_hierarchy` (derived from
  `_children_by_parent`), `root_segment`, `get_children(name)`, `get_segment_chain(name)`.
- `required_keypoints() -> set[str]` — the union over **all** segments (every bone is driven; the face's
  three joined the contract 2026-08-13); this is the set Task 6's completeness contract checks.
- Validators (raise at load): duplicate segment names; exactly one root; every parent exists; no cycles.
  (The old model's twist-source and required-bones validators retire with `HumanBone`.)
- Per SF-AL A5 the model describes **one** human — multi-subject is a list of them and the model grows
  no subject dimension. Per A7, composition replaces the `Actor → Human/Animal/Board` inheritance.
- The old constructor (`from_bone_definitions`, `subject_height_mm`, `t_pose_markers`) is **deleted**,
  not kept — reference geometry is Task 5's job, from measured lengths.

**Composition entry point:** `compose_standard_human(name="standard_human")` builds the 60-segment
human: `compose_parts([(BODY_MIDLINE_PART, ""), (BODY_LIMB_PART, "left_"), (BODY_LIMB_PART, "right_"),
(HAND_PART, "left_"), (HAND_PART, "right_"), (FACE_PART, "")])` — 20 + 32 + 8 = 60, matching
`BONE_ALIASES`. (The `undriven_segments` field from the first build is removed — every segment is
driven; the face's blendshape *channels* are what stay declared-but-null.)

- [x] **Step 1:** Write `test_hand_part_has_sixteen_segments` and
      `test_hand_composes_onto_the_body_by_name_agreement` (assert `left_hand.parent == "left_lower_arm"`
      and that `left_lower_arm` exists in the composed body; 20 + 32 = 52 segments).
- [x] **Step 2:** Run; expected FAIL.
- [x] **Step 3:** Author `hand_part.py` and `face_part.py`.
- [x] **Step 4:** Run; expected PASS (additive — the existing suite stays green).
- [x] **Step 5:** Rewrite `StandardHuman` per the spec above; write `test_standard_human_model.py`
      (60 segments matching `BONE_ALIASES`; `required_keypoints()` = 76 — every segment driven;
      validators: duplicate names, two roots, missing parent, cycle — one test each).
- [x] **Step 6:** Write `test_hierarchy_accessors_agree` — `segment_parents`, children, and
      root-to-segment chains describe the same tree ([`14`](../14-engine-testing-strategy.md) §7).
- [x] **Step 7:** Run; the suite is green **only at the unit's end** (Tasks 5 + 7 land in the same
      pass). Report the unit stopping point.

---

### Task 5: Reference geometry from the T-pose

**Files:**
- Create: `skellyforge/skellymodels/standard_human/reference_geometry.py`
- Test: `skellyforge/tests/test_reference_geometry.py`

Ports `add_rig_by_bone`'s construction, adapted to the canonical frame. **Construction spec** (part of
the Task 4 execution unit — see its unit note):

1. **Euler convention, pinned here:** `rest_rotation` is XYZ **extrinsic**, radians — `R = Rx·Ry·Rz`,
   applied as `rest_dir = R @ [0, 0, 1]`. (Every authored value is single-axis, so this is also the
   only place it matters.)
2. **Origins accumulate through the tree in authoring order:** the root (`hips`) sits at the origin —
   the addon's root-height-from-leg-lengths offset is a *world placement* concern, not a reference-
   geometry one. Per segment: `DISTAL` → parent origin + parent `rest_dir × length`; `ORIGIN` → the
   origin keypoint's already-positioned rest position if an earlier declaration placed it (name
   agreement — e.g. the middle finger's mcp, the hand's long-axis endpoint), else the parent's origin.
   **The reference pose is schematic:** ORIGIN branches carry no fan/width geometry (the finger mcps
   collapse to the hand's origin, the hip joints coincide with `hips_center`); the live solve is
   unaffected — it reads live keypoints. Lengths come from `measured_lengths:
   dict[segment_name, float]` (the estimator, Task 8; the ratios seed it); a missing entry raises a
   descriptive `ValueError` naming every absent segment, before any geometry is built.
3. **Right-side mirroring** (SF-AL A3): for `right_*` segments, negate the Y component of every rest
   position and direction, **then rebuild** frames right-handed — never reflect a basis.
4. **Rest approximate axis** (twist reference at rest): where a twist keypoint is declared, its rest
   position minus the segment's rest origin — **unless that direction is within 1° of the long axis**.
   Fall back to the override table (authored for the LEFT side; mirroring flips Y for the right):
   `hips`/`spine`/`neck`/`head` → +X (anterior — the twist keypoints coincide with the origin or are
   off every chain); `upper_arm` → +Z (elbow flexion axis — `wrist` is collinear at rest);
   `upper_leg` → +Y (knee flexion axis — `ankle` is collinear); `foot` → +Z (up — the foot points +X,
   so the roll reference is vertical, and the heel is off-chain); `toes` → +Y (small toe, lateral).
   Twist-less segments — including the face bones, whose rest axes changed when they became driven
   (eyes +X, jaw ≈12.5° off +Z) — default to +Z, which is non-collinear for all of them. The build
   raises if any result is still within 1° of the long axis — a degenerate reference is an authoring
   error.
5. `SegmentReferenceGeometry` carries `origin` (3,), `basis` (3×3, rows = [long axis, approximate axis,
   third via right-handed cross]), and `length` — **not** a distal point. **Off-chain keypoints**
   (referenced only as the long-axis/twist endpoint of nominal segments — `nose`) have no authoritative
   rest position: the build does **not** emit them in `ReferenceGeometry.keypoints`; fixtures and live
   data supply them. This keeps identity-at-T-pose true for every emitted segment.

- [x] **Step 1:** Write `test_reference_basis_is_right_handed` — assert `det(basis) == +1` for **every**
      segment on **both** sides (SF-AL A3's guard; a left-handed frame is still orthonormal so nothing
      else would catch it).
- [x] **Step 2:** Write `test_reference_geometry_scales_linearly_with_measured_lengths` — double every
      measured length, assert every origin doubles.
- [x] **Step 3:** Write `test_no_segment_has_zero_length_in_the_reference_pose`.
- [x] **Step 4:** Run; expected FAIL.
- [x] **Step 5:** Implement `build_reference_geometry(segments, measured_lengths)` returning a
      `ReferenceGeometry` with `.segments: dict[str, SegmentReferenceGeometry]` — `origin`, `basis`
      (3×3) and `length`, **not** a distal point — and `.keypoints: dict[str, (3,)]`, the rest
      positions of every required keypoint (needed by the solver tests and the stream schema's rest
      pose).
- [x] **Step 6:** Run; expected PASS.
- [x] **Step 7:** Report the stopping point.

---

### Task 6: The required-keypoint contract, per tracker

**Files:**
- Modify: `skellytracker/core/io/tracker_mapping.py`
- Modify: the four `*_to_standard_human_mapping.yaml` files (renamed 2026-08-13 — the
  `to_canonical` filename asserted the retired layer)
- Rename: **done 2026-08-13** — the four YAMLs, the four detector `standard_human_mapping_path()`
  methods, `tracker_mapping.py`'s vocabulary (incl. the D20 typing modernization and
  `canonical_names` → `keypoint_names` property)
- Test: `skellytracker/tests/test_mapping_completeness.py` (new file — `skellytracker/tests/` exists with detector tests + conftest)

- [x] **Step 1:** Write `test_every_tracker_mapping_produces_the_full_required_keypoint_set` —
      parametrized over the two **tracker families** (rtmpose: body+hand; mediapipe: body+hand),
      asserting each family's **union** of produced names covers the model's `required_keypoints()`
      (72). No single mapping covers all 72 — the contract is per-family, and both families must cover
      the same set (D7's lesson). The required set travels as a **golden fixture**
      (`skellytracker/tests/fixtures/standard_human_required_keypoints.txt`, generated from the model —
      the regeneration command is in its header; skellytracker's tests cannot import skellyforge, the
      repo boundary). Expect RED on exactly `mid_sternum`, `head_vertex`, `left_foot_ball`,
      `right_foot_ball`, `jaw` — for BOTH families.
- [x] **Step 2:** Write `test_a_mapping_referencing_an_unproduced_keypoint_raises_at_load` — the
      fail-loud half of D24. This adds a `known_tracker_keypoints: set[str] | None = None` parameter to
      `TrackerMapping.__init__`/`from_yaml`: when provided, every tracker-side name the mapping
      references (string targets, list members, dict keys, anatomical_offset origins/axes/reference
      lengths) must be in the set, else `ValueError` naming the offenders. A keypoint missing *this
      frame* is occlusion and is still skipped silently — the load-time check is about names, not
      frames.
- [x] **Step 3:** Run; expected FAIL — `mid_sternum`, `head_vertex`, `foot_ball` are produced by no mapping.
- [x] **Step 4:** Add `anatomical_offset` definitions for the derived keypoints to **both** body
      mappings, identically (D7: every tracker produces the full set, or the segment model means
      different things depending on which detector ran): `mid_sternum`, `head_vertex`, `foot_ball` —
      and **`jaw`** (the driven face bones joined the contract 2026-08-13). *(Both body mappings
      already produce `left_eye`/`right_eye` 1:1 — verified — so the jaw frame works for both
      trackers.)* Jaw design, §7 provenance:
      origin `nose`; frame up = `neck_center→head_center` (exact), lateral = `left_eye→right_eye`
      (approximate), anterior = up × lateral; offset `up: -0.9, anterior: -0.2` of
      `reference_length: eye_width` (new named length: `left_eye→right_eye`). *Estimated from the
      facial-proportions canon (eye width as the facial-third unit) rather than a published table;
      refine if a sourced value appears.* The offset ratios double as the jaw's rest-direction
      derivation (Task 4) — change one, change the other.
- [x] **Step 5:** Rename the four mapping YAMLs to `{tracker}_to_standard_human_mapping.yaml`; update
      the four detector `standard_human_mapping_path()` references, `tracker_mapping.py`'s docstring and
      identifiers, and the YAML comment language. **Executed 2026-08-13 (early, per the user).**
      freemocap's two mapping-path dicts (`skeleton_rigidifier.py:53`, `center_of_mass.py:62`) still call
      the old method name — they update at the commit round, alongside the push.
- [x] **Step 6:** Run; expected PASS (226 green, both families).
- [ ] **Step 7:** Report the stopping point — **this ends in skellytracker and skellyforge, so nothing
      reaches FreeMoCap until the user commits + pushes, then `uv lock --upgrade-package` + `uv sync`.**

---

### Task 7: Solver reads declared keypoints

> **Part of the Task 4 execution unit** — see Task 4's unit note. The old solver (bones +
> `_get_distal_position` + `TwistPolicy` tiers) and its two test files
> (`test_orientation_solver_composition.py`, `test_orientation_solver_damping.py`) are **replaced** in
> this pass; the new suite is specified below, plus the surviving composition/damping math tests.
> `test_critically_damped_orientation.py` (the D3/D4 filter itself) is unchanged.

**Files:**
- Modify: `skellyforge/kinematics/orientation_solver.py`
- Test: `skellyforge/tests/test_solver_keypoint_declared.py` (new); the two old solver test files are replaced by it + the surviving math tests.

**Solver design (replaces the tier machinery — the declaration IS the policy):**

```
solve_frame_orientations(standard_human, reference_geometry, keypoints, *,
                         timestamp_seconds, previous_result=None)
```

(`reference_geometry` is Task 5's output — the caller builds it from measured lengths, so the solver
stays a pure function of declared data + this frame's keypoints.)

- Input: `keypoints: dict[keypoint_name, (3,) position]` — the tracker's named keypoints, straight
  through. No bone-keyed joint map, no `_BONE_TO_LANDMARK`, no `_get_distal_position`.
- Walk segments in authoring order (hierarchy order by construction). For each segment: resolve
  `origin = keypoints[origin_keypoint]`, `long = keypoints[long_axis_keypoint]`. **Missing either →
  skip this segment this frame** (occlusion is data — the stream's NaN rule covers it; a mapping that
  never produces the keypoint fails at load, Task 6). Coincident positions → skip likewise (the
  load-time name validation makes same-*name* impossible; numeric coincidence is this frame's data).
- **Swing:** `q_swing = rotation_between_vectors(ref_long_axis, live_long_dir)` where `ref_long_axis` is
  the reference geometry's long axis (row 0 of its basis).
- **Twist, two-tier (the declaration IS the policy):**
  1. Twist keypoint declared **and** usable → `twist_dir = normalize(twist_pos − origin)`; if
     `|dot(long_dir, twist_dir)| > cos(5°)` (the singularity gate) it degrades to tier 2. Otherwise
     build the live basis from (long, twist) and `q_world = rotation from ref basis to live basis`
     (undamped — a measured roll).
  2. No twist keypoint, occluded, or gated → **damped minimal roll**: live approximate axis =
     `q_swing` applied to the ref approximate axis; basis rotation; **critically damped** via the
     existing D3/D4 filter (`advance_critically_damped_orientation`, per-segment state carried on
     `FrameOrientationResult.damping_states`, `timestamp_seconds` required with no default — D38).
- `q_local = conj(q_parent_world) * q_child_world` — the D1 composition, unchanged, now applied to the
  solved set. Root's local == its world.
- Keep: `FrameOrientationResult` (world/local wxyz dicts + timestamp + damping states), the
  critically damped filter, `solve_bone_world_orientation`'s zero-length raise (per-segment API).

- [x] **Step 1:** Write `test_every_declared_segment_produces_an_orientation` — feed a full plausible
      keypoint set (T-pose perturbed, including a schematic `nose`), assert one world quaternion for
      **every** segment (**55**; the face bones joined the driven contract 2026-08-13). Today's solver
      returns 16 of 21 because `_get_distal_position` needs a child, so `head`, both hands and both toes
      silently produce nothing.
- [x] **Step 2:** Write `test_a_segment_with_multiple_children_uses_its_declared_long_axis_keypoint` —
      today `hips`' distal is whichever child is declared first, so a reordering silently redirects it.
- [x] **Step 3:** Write `test_leaf_segments_are_solvable` — `head`, `left_hand`, `left_toes`.
- [x] **Step 4:** Write `test_coincident_origin_and_long_axis_keypoints_raise_at_model_load_not_at_solve`
      — the `neck` crash becomes a load-time validation failure (Task 1) instead of a per-frame exception
      that kills the aggregator node.
- [x] **Step 5:** Write the twist tests: a declared twist keypoint resolves a known roll (off-axis
      fixture per doc 14 §2 — never coaxial, never rest-orientation); the singularity gate degrades a
      straight limb to the damped tier; a twist-less segment (finger) holds-and-damps. Pin the gate's
      **threshold boundary** behaviorally (`test_singularity_gate_threshold_boundary` — fixtures that
      straddle cos(5°): the wrist-direction angle is ~0.44× the forearm bend, so 10°/13° bends put it
      inside/outside the gate). **Plus the
      load-bearing contract test** ([`14`](../14-engine-testing-strategy.md) §4): `test_identity_at_t_pose`
      — feed the reference geometry's own keypoint map as live input, assert every solved world AND
      local quaternion is identity. This test caught the ORIGIN-attachment inconsistency in Task 5's
      first build (the finger mcp vs. hand-distal conflict — 180° errors); it is the unit's strongest
      guard.
- [x] **Step 6:** Delete the old solver internals; implement the design above. Replace the two old
      solver test files with the new suite (keep the composition round-trip spirit: recompose every
      `(parent_world, local)` pair == child world; keep the damped-filter tests on the new API).
- [x] **Step 7:** Run; expected PASS. Then run the **whole** suite —
      `uv run --with pytest pytest skellyforge/tests/ -q` — the unit is green only now.
- [x] **Step 8:** Report the stopping point.

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

**Delivered design (2026-08-13):** the class is renamed `SegmentLengthEstimator` (`RollingBoneLengths`
retired with the "bone" vocabulary). Constructor: `segment_endpoints: dict[segment_name,
(origin_keypoint, long_axis_keypoint)]` + `segment_seeds: dict[segment_name, float]` (the
anthropometric ratio × height fallback) + `window_seconds: float | None` (`None` = unbounded — nothing
is ever evicted). `__post_init__` raises if the two dicts name different segments. `update(positions,
*, t)` measures each segment only when both its keypoints are present, appends finite positive lengths,
and evicts samples strictly older than `window_seconds` (skipped when `None`). `lengths` is the
per-segment median, seed when the window is empty; `reset()` clears. Keyed by **segment name** — the
arrow key and both `split("->")` sites (F2) disappear because length is a property of a segment.
`kinematics/__init__.py` exports the new name.

- [x] **Step 1:** Write `test_unbounded_window_reproduces_the_batch_median` — feed a synthetic recording
      with absurd inter-frame gaps, assert the result equals `statistics.median` over all frames.
- [x] **Step 2:** Write `test_rolling_window_drops_samples_older_than_the_window` — a sample exactly at
      the window boundary survives; one strictly older is evicted.
- [x] **Step 3:** Write `test_a_segment_with_no_samples_falls_back_to_its_anthropometric_seed`.
- [x] **Step 4:** Run; expected FAIL.
- [x] **Step 5:** Rewrite per the delivered design above; port the existing rolling-window tests
      (seeds-first, single measurement, median, even-count, missing keypoint, unseen fallback, reset) to
      segment-name keys; add `test_endpoints_and_seeds_must_name_the_same_segments`.
- [x] **Step 6:** Run; expected PASS. **Delete** the FreeMoCap copy
      (`freemocap/core/tasks/mocap/rigid_body/online_segment_lengths.py`) **and its test**
      (`freemocap/tests/rigid_body/test_rolling_bone_lengths.py`) — the skellyforge suite is the
      estimator's test now; keeping the freemocap test would duplicate it. Both are freemocap
      working-tree changes; nothing else imports the copy (verified). freemocap's `skeleton_rigidifier.py`
      import updates at the commit round (Phase D) — the pinned skellyforge still exports the old name
      until then.
- [x] **Step 7:** Report the stopping point.

---

### Task 9: Retire the old models

**Files:**
- Modify: `freemocap/core/pipeline/realtime/realtime_aggregator_node.py:876-1029`
- Delete: `skellyforge/biomechanics/`, `skellyforge/pipelines/dlc_pipeline.py`
- Modify: `skellyforge/skellymodels/tracker_info/canonical_body.yaml`, `canonical_hand.yaml`

- [x] **Step 1:** Delete `_BONE_TO_LANDMARK`, `_standard_human_cache`, `_get_standard_human()`,
      `_build_solver_positions()`; the aggregator loads the composed `StandardHuman` once per run and
      passes keypoints straight through. Closes D11, D12, D16's remainder. **Delivered design
      (2026-08-13, Round-1 leftovers ride along):** the solver's reference geometry needs only correct
      **directions** (lengths do not affect solved quaternions), so it is built once per run from
      nominal seeds (`length_ratio × 1700 mm`); the solver input is the merged rigidified positions —
      body + hands under the model's standard-human names (`RigidifyResult` gains standard-human-keyed
      hand positions; the rigidifier already computes them internally); the rigidifier's three
      `RollingBoneLengths` estimators adapt to `SegmentLengthEstimator` (labels keep the rigidifier's
      internal arrow conventions; `window_seconds=window_s`); and the six `canonical_mapping_path()`
      call sites (4 in `skeleton_rigidifier.py`, 2 in `center_of_mass.py`) become
      `standard_human_mapping_path()`.
- [x] **Step 2:** Delete `skellyforge/biomechanics/` (F5) and `dlc_pipeline.py`.
- [x] **Step 3:** Re-express CoM against segments using **de Leva (1996)** — mass fraction and
      CoM-as-fraction-of-segment-length, referenced to **joint centres**, which is what our origins are.
      Winter's table references bony landmarks, which is why `canonical_body.yaml` needed a `head` segment
      spanning ear-to-ear. Citation:
      de Leva, P. (1996). *Adjustments to Zatsiorsky-Seluyanov's segment inertia parameters.*
      Journal of Biomechanics, 29(9), 1223–1230.
      **Decided 2026-08-13 (user):** default = **`DE_LEVA_MEAN`** (the mean of the female and male
      tables — the module already computes it; `segment_inertial_parameters("female"/"male"/"mean")`
      exposes the per-sex tables, which de Leva's Table 4 defines — no values are dropped). **The
      mass-redistribution policy is KEPT** (mass conservation is correct; the `directly_observed`
      confidence signal stays honest) with its chains re-expressed in de Leva terms. **Segment mapping**
      (documented in code with provenance; de Leva's segments are 8, ours are 55 — every unmapped VRM
      segment carries zero mass inside a mapped span): head(+neck) → `neck_center→head_vertex`; trunk →
      `mid_sternum→hips_center` (suprasternale≈mid_sternum, mid-hip≈hips_center); upper_arm/forearm/hand/
      thigh/shank → our upper_arm/lower_arm/hand-chain (wrist→middle_finger_tip)/upper_leg/lower_leg;
      foot → our foot (`ankle→foot_ball`, metatarsale II) with `toes` mass 0 (inside de Leva's foot);
      hips/spine/chest/upper_chest individually, shoulder, eyes, jaw, fingers: mass 0 (inside the
      trunk/hand masses).
- [ ] **Step 4 (revised 2026-08-13, user):** **no interim stripped state.** Repoint
      `tracker_schema_message.py`'s render connections at the composed segments now. The YAMLs
      (`canonical_body.yaml` / `canonical_hand.yaml`) are **deleted wholesale in Phase E** — their
      remaining readers (the old `AnatomicalStructure`/`ModelInfo` layer, the batch diagnostics
      `segment_lengths.py`, and the realtime rigidifier's seed/`joint_hierarchy` dependency, whose
      re-key onto the model is Phase E's rigidifier work) die with the posthoc rebuild.
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
- The composed standard human is **60 segments** — 55 VRM 1.0 humanoid bones + 5 face-detail segments
  (nose, ears, mouth corners) — matching `BONE_ALIASES`.
- **Every** segment produces an orientation. No silent skips, no first-child inference.
- Every tracker mapping produces the full required keypoint set; a gap fails at load.
- Realtime and posthoc share one length estimator; posthoc passes an unbounded window.
- ROM limits are declared on every major segment (not yet enforced) — values land when Task 5 pins the
  segment local-frame convention (see Task 3's authored-values note).
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
  reconstruction-kinematics best practice before Task 7 locks the solver in. Trigger (re-set 2026-08-13): before
  Phase F — the solver landed without the check, and VMC consumes `ROTATIONS_LOCAL`; the design follows
  the addon + the proven D3/D4 damping, so this is confirmation, not a blocker. Sources: humanoid-IK / marker-set-reconstruction literature
  on twist (roll) resolution for under-constrained segments; the addon's own behaviour (DampedTrack leaves
  roll free unless a LockedTrack removes it) is the working reference.
- **ROM enforcement.** Blender resolves limits by iterating constraints; a closed-form clamp on a
  quaternion solve is not equivalent. Needs its own design once the model lands.
- **`.VRM` export.** Needs the skeleton (this plan), the alias table (exists), and a **skinned mesh** —
  the addon's `skelly_bones.py` maps mesh pieces to bone groups with a nominal `mesh_length` to scale
  against measured lengths. Its own plan, after this one.
