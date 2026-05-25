# Hot-Swappable Backend Pattern

> How to make Rust and Python implementations of the same tracker interchangeable at runtime. Copied from skellycam's `USE_RUST_BACKEND` flag in `camera_group_manager.py`.

## The Problem

During development, you need to compare Rust and Python tracker output side-by-side. In production, you want to fall back to Python if the Rust backend has issues. The switching must be instant, at runtime, with no restart.

### Invariants

- Single boolean flag selects backend
- Switching is instant (hotkey in webcam demo, config flag in production)
- Both backends expose the same interface
- beartype must accept both as valid `BaseTracker` instances
- Unknown backends print a loud warning, don't crash

## Architecture

```
                 ┌─────────────────────────┐
                 │  get_brightest_point_   │
                 │  tracker()              │
                 │                         │
                 │  if USE_RUST_BACKEND:   │
                 │    → Rust adapter       │
                 │  else:                  │
                 │    → Python original    │
                 └──────────┬──────────────┘
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
┌───────────────────────┐     ┌───────────────────────┐
│ RustBrightestPoint    │     │ BrightestPointTracker  │
│ Tracker (BaseTracker) │     │ (BaseTracker)          │
│                       │     │                       │
│ delegates to          │     │ uses detector/        │
│ _skellytracker_rust   │     │ annotator/recorder    │
└───────────────────────┘     └───────────────────────┘
```

## The Adapter Class

```python
class RustBrightestPointTracker(BaseTracker):
    """Subclasses BaseTracker so beartype accepts it anywhere BaseTracker is expected."""

    config: BrightestPointTrackerConfig
    detector: BrightestPointDetector
    annotator: BrightestPointImageAnnotator
    recorder: BaseRecorder | None

    def __init__(self, num_points=1, luminance_threshold=200):
        # Build minimal Python stubs for BaseTracker dataclass fields.
        # These are NEVER used for detection — process/annotate are overridden.
        cfg = BrightestPointTrackerConfig()
        cfg.detector_config.num_tracked_points = num_points
        cfg.detector_config.luminance_threshold = luminance_threshold
        detector = BrightestPointDetector.create(cfg.detector_config)
        annotator = BrightestPointImageAnnotator.create(cfg.annotator_config)
        super().__init__(config=cfg, detector=detector, annotator=annotator, recorder=None)

        native = _get_native()
        self._inner = native.BrightestPointTracker(num_points, luminance_threshold)

    def process_image(self, frame_number, image, record_observation=True):
        return self._inner.process_image(frame_number, image)

    def annotate_image(self, image, observation):
        return self._inner.annotate_image(image, observation)
```

### Why subclass BaseTracker?

beartype runs across the entire skellytracker package. `WebcamDemoViewer.__init__` has:
```python
tracker: BaseTracker = None
```
If `RustBrightestPointTracker` doesn't inherit from `BaseTracker`, beartype rejects it at runtime. Duck-typing is not enough — the type must pass `isinstance()`.

### Why the Python stubs?

`BaseTracker` is a `@dataclass` which auto-generates `__init__` requiring `config`, `detector`, `annotator` fields. The Rust adapter doesn't use these, but must pass them to `super().__init__()` to satisfy the dataclass contract. A `BrightestPointTrackerConfig` with default values and corresponding detector/annotator instances are created as lightweight stubs.

## WebcamDemoViewer Integration

```python
# New hotkey constant
KEY_TOGGLE_RUST_BACKEND = ord("r")

# In __init__
self.use_rust_backend: bool = True

# Hotkey handler — instant swap for BrightestPoint
elif key == KEY_TOGGLE_RUST_BACKEND:
    self.use_rust_backend = not self.use_rust_backend
    if "brightestpoint" in self.tracker.__class__.__name__.lower():
        if self.use_rust_backend:
            self.tracker = RustBrightestPointTracker.create()
        else:
            self.tracker = BrightestPointTracker.create()
    else:
        logger.warning(f"NOT IMPLEMENTED: {tracker_name} has no Rust backend")
```

And the `b` key for BrightestPointTracker respects the flag:
```python
elif key == KEY_USE_BRIGHTEST_POINT_TRACKER:
    if self.use_rust_backend:
        self.tracker = RustBrightestPointTracker.create()
    else:
        self.tracker = BrightestPointTracker.create()
```

## Factory Function

```python
USE_RUST_BACKEND: bool = True

def get_brightest_point_tracker(num_points=1, luminance_threshold=200):
    if USE_RUST_BACKEND:
        return RustBrightestPointTracker(num_points=num_points, luminance_threshold=luminance_threshold)
    else:
        from skellytracker.trackers.brightest_point_tracker.brightest_point_tracker import (
            BrightestPointTracker,
        )
        return BrightestPointTracker(num_points=num_points, luminance_threshold=luminance_threshold)
```

## Guidance for Next Trackers

1. **Every Rust tracker needs an adapter class** — subclass `BaseTracker`, override `process_image` + `annotate_image`, provide Python stubs for dataclass fields
2. **Add a hotkey** — one key per tracker backend toggle (e.g., `r` for BrightestPoint, could add shift+r for Charuco)
3. **NOT IMPLEMENTED warning** — when a tracker has no Rust backend yet, pressing its toggle key should warn, not crash
4. **Keep the factory function** — `get_<tracker_name>()` with `USE_RUST_BACKEND` flag. Callers don't know which backend they get.
5. **`.create()` classmethod** — match the Python tracker's `create(config)` interface for drop-in compatibility
