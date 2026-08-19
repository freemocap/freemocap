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
    axis: Literal["x","y","z","-x","-y","-z"]       # which basis row, signed
    target_landmark: str                            # origin -> target direction
    rest_direction: tuple[float, float, float] | None = None  # world direction at T-pose

@dataclass(frozen=True, slots=True)
class RigidBodySegment:
    name: str
    parent: "RigidBodySegment | None"              # object after load
    landmarks: tuple[AnatomicalLandmark, ...]      # objects after load
    origin_landmark: AnatomicalLandmark            # object after load
    axes: tuple[AxisDefinition, ...]               # FIRST = primary, SECOND = twist
    rigid_with_parent: bool = False

    @property
    def length(self) -> float:
        # |primary target's rest_position| — origin is (0,0,0) in this segment's
        # own frame by construction.
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
    linkages: tuple[JointLinkage, ...]             # derived from parent edges
    chains: tuple[KinematicChain, ...]

@dataclass(frozen=True, slots=True)
class StandardHumanTPose:                          # the WHOLE built reference
    segments: dict[str, SegmentTposeGeometry]       # per-segment origin/basis/length
    landmarks: dict[str, NDArray[np.float64]]       # per-landmark rest-world position

class FaceBlendShapes:                              # 52 ARKit blendshapes (NOT segments)
    name: str
    blendshapes: dict[str, float]
```

## Parts + sidedness

The real definitions are split into **flat part files** (`pelvis.yaml`, `axial.yaml`, `arm.yaml`,
`hand.yaml`, `leg.yaml`, `foot.yaml`), listed by the top-level `standard_human.yaml`:

```yaml
name: standard_human
parts:
  pelvis: {$include: pelvis.yaml}
  axial:  {$include: axial.yaml}
  arm:    {$include: arm.yaml}   # sided: true -> instantiated left_ + right_
  hand:   {$include: hand.yaml}
  leg:    {$include: leg.yaml}
  foot:   {$include: foot.yaml}
```

A **midline** part is used once; a **sided** part (`sided: true`) is authored with generic names and
instantiated `left_* + right_*`, the right side Y-mirrored. Shared joints (`hip`, `knee`, `wrist`) are
defined once with explicit `left_`/`right_` names in the midline/parent part and referenced by generic
name in the sided part (name agreement).

The **face is not a part** — it is 52 ARKit blend shapes in `face.yaml`, loaded separately as
`FaceBlendShapes` (the eyes / ears / nose are LANDMARKS on the head, not segments).

## The leg, in YAML (local-frame authoring)

```yaml
# leg.yaml (sided: true — authored once, instantiated left_upper_leg / right_upper_leg …)
landmarks:
  knee:                     {definition: "Center of the knee joint",                           reference_frame: upper_leg, rest_position: [0, 429, 0]}
  greater_trochanter:       {definition: "Tip of the greater trochanter",                       reference_frame: upper_leg, rest_position: [20, -20, 0]}
  lateral_femoral_condyle:  {definition: "Most lateral point of the lateral femoral condyle",   reference_frame: upper_leg, rest_position: [20, 429, 0]}
  medial_femoral_condyle:   {definition: "Most medial point of the medial femoral condyle",     reference_frame: upper_leg, rest_position: [-20, 429, 0]}
  ankle:                    {definition: "Center of the ankle joint",                          reference_frame: lower_leg,  rest_position: [0, 430, 0]}
  tibial_tuberosity:        {definition: "Most anterior point of the tibial tuberosity",        reference_frame: lower_leg,  rest_position: [0, 60, -10]}
  lateral_malleolus:        {definition: "Most lateral point of the lateral malleolus",         reference_frame: lower_leg,  rest_position: [15, 430, 0]}
  medial_malleolus:         {definition: "Most medial point of the medial malleolus",           reference_frame: lower_leg,  rest_position: [-15, 430, 0]}

segments:
  upper_leg:
    parent: pelvis
    origin_landmark: hip               # hip is authored in pelvis.yaml (left_hip / right_hip)
    landmarks: [hip, knee, greater_trochanter, lateral_femoral_condyle, medial_femoral_condyle]
    axes:
      - {axis: y, target_landmark: knee, rest_direction: [0, 0, -1]}                  # primary: +Y toward the knee; world −Z (down) at T-pose
      - {axis: x, target_landmark: lateral_femoral_condyle, rest_direction: [0, 1, 0]} # twist: +X lateral; world +Y (left) at T-pose
  lower_leg:
    parent: upper_leg
    origin_landmark: knee
    landmarks: [knee, ankle, tibial_tuberosity, lateral_malleolus, medial_malleolus]
    axes:
      - {axis: y, target_landmark: ankle, rest_direction: [0, 0, -1]}
      - {axis: x, target_landmark: lateral_malleolus, rest_direction: [0, 1, 0]}

chains:
  leg: {start: pelvis, end: foot}     # pelvis → upper_leg → lower_leg → foot
```

> `rest_position` is authored **once**, in its `reference_frame`'s LOCAL frame. The primary direction
> (`axes[0]`) sits on `y` with `+Y` toward the child; `rest_direction` is that axis's WORLD unit
> direction at the T-pose (legs point down: `[0,0,-1]`). `left_knee` is `[0,429,0]` in
> `left_upper_leg`'s frame; `left_lower_leg` references it as `origin_landmark` and inherits it as its
> local `(0,0,0)` **by construction** — no duplication. Sidedness turns `knee` → `left_knee` /
> `right_knee`; the right side negates only `rest_direction`'s Y, never `rest_position`.

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
    config = SkeletonConfig.from_dict(cfg)               # cls(**data), no string-key indexing
    landmark_cfgs, segment_cfgs, chain_cfgs = _compose_parts(config.parts)
    # pass 1: landmarks (objects)
    landmarks = {n: AnatomicalLandmark.from_config(n, c) for n, c in landmark_cfgs.items()}
    # pass 2: segments — resolve parent / landmarks / origin_landmark names → objects
    #         (KeyError on an unknown name = the typo's exact line)
    segments = resolve_segments(segment_cfgs, landmarks)
    # pass 3: linkages derived from parent edges; chains = start→end paths
    linkages = derive_linkages(tuple(segments.values()))  # child.origin_landmark IS the shared point
    chains = tuple(KinematicChain(n, segs[c.start], segs[c.end])
                   for n, c in chain_cfgs.items())
    return cls(config.name, tuple(segments.values()), linkages, chains)
```

## The compiled objects

```python
>>> skeleton = HumanSkeleton.standard_human()       # 95 segments / 94 linkages / 25 chains
>>> upper_leg = skeleton.segment("left_upper_leg")
>>> upper_leg.parent                    # → <RigidBodySegment "pelvis">          (object)
>>> upper_leg.origin_landmark           # → <AnatomicalLandmark "left_hip">       (object)
>>> upper_leg.origin_landmark.reference_frame  # → "pelvis"
>>> upper_leg.length                    # → 429.0  (‖[0,429,0]‖)

>>> linkage = next(l for l in skeleton.linkages if l.name == "left_knee")
>>> linkage.parent_segment              # → <RigidBodySegment "left_upper_leg">
>>> linkage.child_segment               # → <RigidBodySegment "left_lower_leg">
>>> linkage.shared_landmark             # → <AnatomicalLandmark "left_knee">

>>> leg = skeleton.chain("left_leg")
>>> leg.segments   # → (pelvis, left_upper_leg, left_lower_leg, left_foot)
```

## Branching: the wrist fan

A branch is several chains that descend from one common ancestor:

```yaml
chains:
  thumb:         {start: thumb_metacarpal,         end: thumb_distal_phalanx}
  index_finger:  {start: index_finger_metacarpal,  end: index_finger_distal_phalanx}
  middle_finger: {start: middle_finger_metacarpal, end: middle_finger_distal_phalanx}
  ring_finger:   {start: ring_finger_metacarpal,   end: ring_finger_distal_phalanx}
  pinky_finger:  {start: pinky_finger_metacarpal,  end: pinky_finger_distal_phalanx}
```

Each `KinematicChain.segments` is the path `metacarpal → … → distal phalanx`; the five chains share the
`hand` segment (the carpus) as their common ancestor — exactly the branching structure FABRIK reconciles.
The same fan shape repeats at the foot (five metatarsal → phalanx chains under the tarsus).
