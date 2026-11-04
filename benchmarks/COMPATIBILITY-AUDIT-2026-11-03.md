# Cross-platform compatibility audit — 2026-11-03

The owner's requirement is maximum compatibility across hardware. A missing implementation,
failed test, or unavailable dependency is engineering work to resolve, not permission to
exclude an entire operating system. Platform-specific adapters remain necessary where APIs,
ABIs or hardware capabilities differ. They must preserve the intended user-facing behavior.

## Scope and evidence

Inspected current first-party Python, Rust, TypeScript/Electron, package declarations,
installer configuration, workflows and relevant tests in Core, SkellyCam, SkellyTracker,
SkellyForge, the Blender add-on and shared utilities. The initial source/manifest search
identified 117 platform/architecture references, followed by targeted inspection of hidden
CI workflows, native target tables, Windows wheel tags and test helpers. This is a source
audit, not proof that every device or OS has been exercised. Third-party implementation
internals, historical worktrees and generated bundles are not audited here.

Core inspection/fixes use `sfn26-machine-benchmarks` based on `5b6adb51`. Dependency snapshots:
SkellyCam `e7eeda45`, Tracker `089c8eaa`, Forge `a54761f1`, add-on `aefde7da`.
Existing local lockfile differences were preserved. Other agents' UI checkouts were not edited.

## Confirmed defects fixed here

| Defect | Owning source | Reproduction and correction |
|---|---|---|
| Automatic Blender packaging rejected every non-Windows/x64 runtime before calling a builder that already knows Mac/Linux targets | `freemocap/core/blender/local_package.py` | Full standard test-data command failed on Blender 5.2.1/Python 3.13/macOS ARM64. Core now checks the Blender/Python ABI and delegates platform capability to the installed add-on builder's `PLATFORMS`. Mac ARM64/Intel, Linux x64 and Windows dispatch tests cover routing, cache validation and unknown-runtime rejection. Actual Mac automatic setup/export/reopen validation passed. |
| Offline automatic-install and frozen-backend test fixtures always seeded Windows wheels | `freemocap/tests/blender_test_dependency.py`, `test_blender_automatic_integration.py`, `test_blender_frozen_integration.py` | `seed_wheels` hard-coded `{python}-windows-x64.json`. It now uses the inspected Blender OS/architecture/Python. Regression cases cover Mac ARM64/Intel, Linux x64 and Windows. These tests validate selection; they do not claim a frozen installer has been executed on every platform. |
| Windows-path regression test changed global `os.name`, breaking filelock/pathlib on Mac | `freemocap/tests/test_dataset_workflow.py` | Fixed in the preceding benchmark commit by limiting the simulated OS to the tested module. |

The first two failures belong to Core coordination/testing. No add-on code change or manual
ZIP installation was necessary to make the existing full Mac workflow work.

## Remaining exclusions and capability gaps

These are open engineering findings, not accepted platform exclusions. No blanket success
claim is made for their affected hardware. Paths below are relative to their owning repo.

| Priority | Owner / path | Confirmed behavior | Required correction and acceptance |
|---|---|---|---|
| High | Core and Tracker `pyproject.toml`, `[tool.uv].environments` | Linux is restricted to `x86_64`; Windows to `AMD64`. Mac is included without architecture filtering. | Resolve the dependency/preset graph for ARM rather than merely deleting markers and breaking universal resolution. Validate clean installs and ordinary processing for each target; record actual third-party wheel/build gaps. |
| High | Core `.github/workflows/build-installers-pyinstaller.yml` | Explicit comment says Linux ARM is intentionally not built because of MediaPipe and says not to re-add it until wheels exist. Build matrix has Windows x64, Linux x64 and Mac ARM64 only. | Make optional detector availability independent of basic application installation, establish an ARM-capable processing path, then build and run installer acceptance on ARM. Missing one detector must not silently remove the whole target. The comment is evidence of an existing shortcut, not current owner policy. |
| High | SkellyCam `skellycam/core/camera/opencv/opencv_helpers/opencv_apply_config.py::_apply_exposure`; `camera_group/camera_backend_manager.py::_create_or_update` | Linux forcibly selects AUTO regardless of requested manual exposure; RECOMMEND is converted to AUTO and recommendation is skipped. | Implement the actual backend's exposure-unit/control conversion and capability checks. Preserve manual/recommendation semantics, test V4L2 and DirectShow separately, and validate hardware brightness/control responses. Do not send Windows log2 exposure values to a different unit system. |
| High | SkellyCam `skellycam/core/device_detection/detect_cameras_devices.py::detect_available_cameras` | On Windows/Linux, enumeration drops every device without VID/PID; only Mac is exempt. | Enumerate valid devices using available stable identity/path/index instead of treating USB metadata as a universal camera prerequisite. Test non-USB/embedded/metadata-poor devices and collision handling. Existing `CameraDeviceInfo` already permits missing VID/PID and has path/index fallbacks. |
| High | SkellyCam `skellycam/core/camera/opencv/opencv_helpers/opencv_apply_config.py::apply_camera_configuration` | `should_apply_framerate = False` disables frame-rate requests on all platforms. This is not an OS gate, but was found while tracing the measured Mac shortfall. | Restore negotiated frame-rate application and report actual device settings. Add request/change tests and rerun the hardware suite. The observed ~20 fps is not yet proven to have this single cause. |
| Medium | Add-on `freemocap_blender_addon/_host_tools/build_addon.py::PLATFORMS` | Lists Windows x64, Linux x64, Mac x64 and Mac ARM64; no Windows ARM64 or Linux ARM64 entries. | Add verified wheel-target/dependency handling and runtime acceptance for ARM, including correct ABI tags. Do not claim a build works by merely inserting a platform label. |
| Medium | Add-on `.github/workflows/create_addon_install_zip.yaml` | Standalone release matrix builds only `windows-x64`, despite a builder with Mac/Linux declarations. Offline tests do run on all three OS families, but do not run Blender. | Extend release jobs alongside runtime install/export/reopen acceptance. Core's automatic preparation is independent of this release workflow, so this does not explain the fixed Core guard. |
| Medium | Core `freemocap-ui/electron-builder.json`; Core/SkellyCam installer workflows | Core Mac targets are ARM64 only; Windows is x64 only. SkellyCam covers Mac Intel/ARM and Linux x64/ARM, but Windows ARM is absent. Native SkellyCam build target mapping already includes Windows ARM64. | Align actual backend builds, Electron architecture, artifact naming/signing and runtime smoke tests. Packaging configurations alone are not evidence of working installers. |
| Medium | Core `freemocap/core/pipeline/dataflow/application_pipeline.py::resolve_tracking_provider`; Tracker `skellytracker/core/sessions/ort_session_utils.py::auto_detect_provider` | Core graph Auto formerly chose CUDA else CPU. The benchmark follow-up now preserves CUDA preference and delegates other hardware to Tracker discovery; full Mac CoreML test/sample processing is verified in the CoreML benchmark report. Tracker Auto still omits DirectML although explicit DirectML exists. | Reconcile application/provider policy with actual model compatibility and prepared-session behavior; validate parity and startup/runtime performance per backend. Earlier Mac records are CPU by the former policy; new CoreML records measure the corrected path. Avoid accidentally restoring unwanted TensorRT compilation while fixing other providers. |
| Medium | Core `freemocap/core/blender/local_package.py::TARGETS`; add-on `tools/build_release.py::TARGETS` | Only Blender 3.0, 3.6, 4.2, 4.5 and 5.2 are declared; intervening versions are rejected even before a package is attempted. | Validate runtime/API/ABI intervals and extend coverage systematically. ABI validation itself is necessary; a sparse tested-version list is not a permanent compatibility policy. |
| Medium | SkellyCam `skellycam/core/recorders/videos/fourcc_codec_helpers.py::_probe_codec` | Uses SIGALRM on all non-Windows systems. `signal.signal` runs before the try/finally, so invocation from a non-main thread would fail before normal fallback/cleanup. Windows gets no equivalent timeout. | Trace active callers, reproduce thread use, and use a bounded probe mechanism usable across OS/thread contexts. This is a source-level hazard, not a reproduced camera-suite failure. |

Core's installer comment currently asserts a particular MediaPipe wheel limitation. This
audit records the code's rationale; it does not claim fresh verification of every current
PyPI wheel. The correct next step is to inspect the actual dependency graph and available
artifacts, then implement and test the target instead of retaining an exclusion indefinitely.

## Platform branches that preserve compatibility

These inspected branches are adapters or integrity checks, not blanket disable switches:

- Windows DLL-directory isolation around Blender spawning; non-Windows library-path cleanup.
- Windows shared-file/replacement semantics versus POSIX file handling; their OS-specific tests.
- Rust JPEG FFI integer widths for LLP64 versus LP64 and native capture library/link selection.
- OpenCV DirectShow/V4L2/AVFoundation selection with fallback, subject to actual backend availability.
- CUDA library names on Windows/Linux, CoreML on macOS, DirectML dependency on Windows. Other
  providers/CPU keep the application usable; a vendor API's platform restriction is not an
  application-wide restriction.
- Native server executable suffixes, executable bits, application IDs, menu conventions,
  file-open commands, GPU inventory and telemetry platform reporting.
- Windows process-start staggering and bytecode warmup are optimizations, not a refusal to run elsewhere.

No new runtime/platform allowlist was introduced to hide a failure. The real full standard
workflow remains the acceptance test for the repaired Mac Blender path.

## Verification of the repaired path

- Full standard test-data run: passed in 67.55 seconds, including automatic first-use setup.
- Full standard sample-data run: passed in 245.85 seconds with the prepared package reused.
- 55 focused tests passed; the four opt-in scene tests were subsequently executed with
  real output fixtures and all passed, including rejection of corrupted landmark and
  armature motion. Source scenes remained unchanged.
- Ruff and `git diff --check` passed. Actual Windows/Linux Blender execution and frozen
  packaging were not performed on this Mac; dispatch/fixture tests cover their boundaries.
