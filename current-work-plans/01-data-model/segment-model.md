# The Standard-Human Definition (YAML + classes)

The standard human is defined in **YAML** and compiled into first-class objects whose references are
objects, not strings. This is the worked example behind [the ontology](../ontology.md).

## The classes

```python
@dataclass(frozen=True, slots=True)
class AnatomicalLandmark:
    name: str
    anatomical_definition: str
    rest_position: tuple[float, float, float]      # in reference_frame's local frame
    reference_frame: str                            # the OWNING segment name

@dataclass(frozen=True, slots=True)
class AxisDefinition:
    axis: Literal["x","y","z","-x","-y","-z"]
    target_landmark: str
    rest_direction: tuple[float, float, float] | None = None

@dataclass(frozen=True, slots=True)
class RigidBodySegment:
    name: str
    parent: "RigidBodySegment | None"              # object after load
    landmarks: tuple[AnatomicalLandmark, ...]      # objects after load
    origin_landmark: AnatomicalLandmark            # object after load
    axes: tuple[AxisDefinition, ...]
    rigid_with_parent: bool = False

    @property
    def length(self) -> float:
        # origin_landmark is (0,0,0) in THIS segment's frame by construction,
        # so length is the distal landmark's |rest_position|.
        ...

@dataclass(frozen=True, slots=True)
class JointLinkage:                                # derived, not authored
    name: str                                      # the shared landmark's name
    parent_segment: RigidBodySegment
    child_segment: RigidBodySegment
    shared_landmark: AnatomicalLandmark

@dataclass(frozen=True, slots=True)
class KinematicChain:
    name: str
    start_segment: RigidBodySegment
    end_segment: RigidBodySegment

    @property
    def segments(self) -> tuple[RigidBodySegment, ...]:
        # walk parent edges from end_segment back up to start_segment, reversed

@dataclass(frozen=True, slots=True)
class HumanSkeleton:
    name: str
    segments: tuple[RigidBodySegment, ...]
    chains: tuple[KinematicChain, ...]

@dataclass(frozen=True, slots=True)
class StandardHumanTPose:                          # the WHOLE built reference
    segments: dict[str, <per-segment reference geometry>]  # origin/basis/length
    landmarks: dict[str, tuple[float, float, float]]

class FaceBlendShapes:                              # 52 ARKit blendshapes (NOT segments)
    name: str
    blendshapes: dict[str, float]
```

## Parts + sidedness

The real definitions are split into **flat part files** (`pelvis.yaml`, `axial.yaml`, `arm.yaml`,
`hand.yaml`, `leg.yaml`, `foot.yaml`, `face.yaml`), listed by the top-level `standard_human.yaml`:

```yaml
parts:
  pelvis: {$include: pelvis.yaml}
  axial:  {$include: axial.yaml}
  arm:    {$include: arm.yaml}   # sided: true -> instantiated left_ + right_
  ...
```

A **midline** part is used once; a **sided** part (`sided: true`) is authored with generic names and
instantiated `left_* + right_*`, the right side Y-mirrored. Shared joints (`hip`, `knee`, `wrist`) are
defined once with explicit `left_/`right_` names in the midline/parent part and referenced by generic name
in the sided part (name agreement).

## The leg, in YAML (simplified, pre-parts)

```yaml
landmarks:
  hips_center:  {definition: "midpoint of the two hip joint centers", reference_frame: hips,            rest_position: [0, 0, 0]}
  trunk_center: {definition: "midpoint of the two hip joint centers at the iliac crest", reference_frame: hips, rest_position: [0, 0, 254]}
  left_hip:     {definition: "left femoral head center",                reference_frame: hips,            rest_position: [0, 88, 0]}
  right_hip:    {definition: "right femoral head center",               reference_frame: hips,            rest_position: [0, -88, 0]}
  left_knee:    {definition: "midpoint of the intercondylar fossa",     reference_frame: left_upper_leg,   rest_position: [0, 0, -429]}
  left_ankle:   {definition: "talocrural joint center",                 reference_frame: left_lower_leg,   rest_position: [0, 0, -430]}
  left_foot_ball: {definition: "first metatarsophalangeal joint",       reference_frame: left_foot,        rest_position: [45, 0, 0]}
  left_heel:    {definition: "posterior calcaneal tuberosity",          reference_frame: left_foot,        rest_position: [0, 0, 0]}

segments:
  hips:
    parent: null
    origin_landmark: hips_center
    landmarks: [hips_center, trunk_center, left_hip, right_hip]
    axes:
      - {axis: y, target_landmark: trunk_center, rest_direction: [0,0,1]}
      - {axis: x, target_landmark: right_hip, rest_direction: [1,0,0]}
  left_upper_leg:
    parent: hips
    origin_landmark: left_hip
    landmarks: [left_hip, left_knee]
    axes:
      - {axis: y, target_landmark: left_knee, rest_direction: [0,0,-1]}
  left_lower_leg:
    parent: left_upper_leg
    origin_landmark: left_knee
    landmarks: [left_knee, left_ankle]
    axes:
      - {axis: y, target_landmark: left_ankle, rest_direction: [0,0,-1]}
  left_foot:
    parent: left_lower_leg
    origin_landmark: left_ankle
    landmarks: [left_ankle, left_foot_ball, left_heel]
    axes:
      - {axis: y, target_landmark: left_foot_ball, rest_direction: [1,0,0]}
      - {axis: z, target_landmark: left_heel, rest_direction: [0,0,-1]}

chains:
  left_leg: {start: hips, end: left_toes}
```

> Note: `rest_position` values are **mm in the local frame of `reference_frame`**, authored once.
> `left_knee` is `[0,0,-429]` in `left_upper_leg`'s frame; `left_lower_leg` references it as its
> `origin_landmark` and inherits it as its local `(0,0,0)` **by construction** — no duplication.

## Loading (three passes, fail-loud)

```python
def load_config(node, base: Path):
    # $include: a dict with the single key "$include" loads that file in place
    if isinstance(node, dict) and set(node) == {"$include"}:
        p = base / node["$include"]
        return load_config(yaml.safe_load(p.read_text()), p.parent)
    if isinstance(node, list):  return [load_config(v, base) for v in node]
    if isinstance(node, dict):  return {k: load_config(v, base) for k, v in node.items()}
    return node

@classmethod
def from_yaml(cls, path: Path) -> "HumanSkeleton":
    cfg = load_config(yaml.safe_load(path.read_text()), path.parent)
    # pass 1: landmarks (objects)
    landmarks = {n: AnatomicalLandmark(name=n, **c) for n, c in cfg["landmarks"].items()}
    # pass 2: segments — resolve parent / landmarks / origin_landmark names → objects
    #         (KeyError on an unknown name = the typo's exact line)
    segments = resolve_segments(cfg["segments"], landmarks)
    # pass 3: linkages derived from parent edges; chains = start→end paths
    linkages = derive_linkages(segments)          # child.origin_landmark IS the shared point
    chains = tuple(KinematicChain(n, segs[c["start"]], segs[c["end"]])
                   for n, c in cfg.get("chains", {}).items())
    return cls(cfg["name"], tuple(segments.values()), chains)
```

## The compiled objects

```python
>>> skeleton = HumanSkeleton.from_yaml("standard_human.yaml")
>>> upper_leg = skeleton.segment("left_upper_leg")
>>> upper_leg.parent                    # → <RigidBodySegment "hips">          (object)
>>> upper_leg.origin_landmark           # → <AnatomicalLandmark "left_hip">     (object)
>>> upper_leg.origin_landmark.reference_frame  # → "hips"
>>> upper_leg.length                    # → 429.0  (‖[0,0,-429]‖)

>>> linkage = skeleton.linkage("left_knee")
>>> linkage.parent_segment              # → <RigidBodySegment "left_upper_leg">
>>> linkage.child_segment               # → <RigidBodySegment "left_lower_leg">
>>> linkage.shared_landmark             # → <AnatomicalLandmark "left_knee">

>>> leg = skeleton.chain("left_leg")
>>> leg.segments   # → (hips, left_upper_leg, left_lower_leg, left_foot, left_toes)
```

## Branching: the wrist fan

A branch is several chains sharing a `start`:

```yaml
chains:
  left_thumb:  {start: left_hand, end: left_thumb_distal}
  left_index:  {start: left_hand, end: left_index_distal}
  left_middle: {start: left_hand, end: left_middle_distal}
  left_ring:   {start: left_hand, end: left_ring_distal}
  left_little: {start: left_hand, end: left_little_distal}
```

Each `KinematicChain.segments` is the path `left_hand → … → fingertip`; the five chains share the
`left_hand` segment, which is exactly the branching structure FABRIK reconciles.
