# Tracker Trait Architecture

> Step 4 (Design Rust Architecture) applied to skellytracker's core framework.

## The Problem

skellytracker needs a common interface for all pose trackers: run inference on an image, produce structured detection results, and draw annotations. Trackers should optionally decompose into separate `Detector` / `Annotator` / `Recorder` components.

### Invariants

- Every tracker processes `(frame_number, image)` → `Observation`
- Every observation carries a `PointCloud` (named landmarks + XYZ coords + visibility)
- Annotation takes `(image, observation)` → annotated image (must NOT re-run detection)
- Optional decomposition: `Tracker` can compose `Detector` + `Annotator`
- Recorder collects observations across frames for serialization
- JSON serialization must produce the same shape as Python's `BaseObservation.to_json_string()`

## Python's Solution

```python
@dataclass
class BaseTracker(ABC):
    config: BaseTrackerConfig
    detector: BaseDetector
    annotator: BaseImageAnnotator
    recorder: BaseRecorder | None = None

    def process_image(self, frame_number, image, record_observation=True):
        obs = self.detector.detect(image=image, frame_number=frame_number)
        if record_observation and self.recorder is not None:
            self.recorder.add_observation(observation=obs)
        return obs

    def annotate_image(self, image, observation):
        return self.annotator.annotate_image(image=image, observation=observation)
```

### Why This Architecture

- Python uses abstract base classes (`ABC`) with dataclass fields
- Pydantic `BaseModel` for config validation
- `beartype` runtime type checking enforces type hints at boundaries
- Runtime duck-typing via `isinstance()` and `hasattr()`
- Detection and annotation are separated to allow composition

## Rust's Solution

### Traits replace abstract classes

```rust
pub trait Observation: Send + Any {
    fn frame_number(&self) -> u64;
    fn point_cloud(&self) -> &PointCloud;
    fn to_json(&self) -> String;
    fn as_any(&self) -> &dyn Any;  // downcasting for tracker-specific data
}

pub trait Tracker {
    fn process_image(&mut self, frame_number: u64, image: &Mat) -> Box<dyn Observation>;
    fn annotate_image(&self, image: &Mat, obs: &dyn Observation) -> Mat;
}
```

### Key differences from Python

| Concern | Python | Rust | Why |
|---------|--------|------|-----|
| Framework type | Abstract class with dataclass | Trait | No inheritance tax, no dataclass field requirements |
| Downcasting | `isinstance(obs, BrightestPointObservation)` | `obs.as_any().downcast_ref::<T>()` | Explicit, opt-in, zero-cost at trait level |
| Config validation | Pydantic `BaseModel` | `#[derive(Deserialize)]` + serde | Compile-time struct shape, runtime value parsing |
| Array data | `numpy` ndarray | `ndarray::Array2<f64>` | Same row-major layout, zero Python overhead |
| Type checking | beartype at runtime | Compile-time — type system | No runtime overhead, caught before execution |
| Recorder | Abstract class, unbounded list | Concrete struct, explicit `.add()` | Simple, no inheritance needed |

### What disappeared

- **ABC + @dataclass combination** — traits replace ABC, plain structs replace dataclasses
- **beartype decoration** — the compiler checks everything at build time
- **`hasattr` / `isinstance` guards** — trait bounds are compile-time guarantees
- **Pydantic model_dump()** — `#[derive(Serialize)]` generates JSON directly

### PointCloud: the canonical data type

```rust
pub struct PointCloud {
    pub names: Vec<String>,              // ordered point names
    pub xyz: Array2<f64>,                // (N, 3) coordinates
    pub visibility: Array1<f64>,         // (N,) confidence scores
    name_to_idx: HashMap<String, usize>, // internal lookup, not serialized
}
```

Invariant: the i-th name corresponds to the i-th row of xyz and the i-th element of visibility. This is enforced at construction time with shape assertions. The Python version has the same invariant but enforces it only at runtime.

### Recorder

```rust
pub struct Recorder {
    observations: Vec<Box<dyn Observation>>,
}
```

Same append-and-serialize pattern as Python. NPY output uses `ndarray-npy`, JSON uses `serde_json`. No pickle — data is typed through the `Observation` trait.

### Guidance for next trackers

1. **Implement `Observation` first** — the trait is small (4 methods), get it right
2. **Implement `Tracker` second** — compose `process_image` + `annotate_image`
3. **Optional `Detector` / `Annotator` decomposition** — only if the tracker benefits from separation (e.g. Charuco where detection and annotation want different config)
4. **Always add `as_any()` support** — needed for downcasting in bridge/annotation code (e.g. accessing contour data for blob outlines)
5. **Keep `PointCloud` as the canonical output** — it's the universal format. Don't invent tracker-specific coordinate representations.
