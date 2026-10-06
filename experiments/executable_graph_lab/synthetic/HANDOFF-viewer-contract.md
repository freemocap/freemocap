# Handoff: backend work needed by the viewer

## Backend completion — 2026-10-05

- Implemented `DiskFile` / `Node.io_files`, all five validation categories,
  absolute-path and placeholder validation, and expanded-camera writer collision
  checks. Paths participate in graph identity and survive partition export.
- Chose **B without a manifest**: `encode` owns each camera video;
  `video_output` is sealed in-memory bookkeeping.
- Kept configuration/API shape unchanged. Paths derive from
  `SYNTHETIC_RECORDING_ROOT`, without creating that directory or its files.
- Used core's current `RecordingStructure` layout (`videos/synchronized`,
  `videos/annotated`, recording-root data Parquet / calibration TOML), rather
  than the historical directory examples below. Camera filenames remain
  synthetic placeholders.
- `viewer.html` was not edited. SHA256 remains
  `142761F8475AFC0781BBFD5C02510C03BBDE0D62382B54C39B32B131E44170E8`.
- All 16 tests pass. Browser verification found no contract banner, confirmed
  filenames and the scientific folder's full-path popup, and checked camera
  substitution. All four `*-proof.jpg` images were retaken.

The original handoff below is retained as the contract and design context.

**From:** viewer/UX pass on `viewer.html`
**To:** backend owner of `graph.py`, `engine.py`, `server.py`, `test_lab.py`
**Status:** the viewer is done and waiting on one backend field (`io_files`) and one graph decision (duplicate save in the annotation branch).

The viewer stays a pure renderer. It authors no topology, paths or positions; everything below comes from `Plan.describe()` and the run snapshot. Please don't edit `viewer.html` to make these work. Change the backend, and ping the UX side if a contract field below has to change shape.

---

## 1. Required: declare disk files on every disk node (`io_files`)

### What the viewer shows today

Every node with `io_role` `read` or `write` draws a disk terminal: a folder joined to the card by a double rail, labelled `LOAD FROM DISK` (blue, arrow out of the folder) or `SAVE TO DISK` (purple, arrow into the folder). The folder lists the file names; clicking it opens the full paths. The inspector lists the same files.

With the current backend, no node declares files, so all 5 disk nodes render a red dashed folder reading `no path declared`, and a red banner lists them:

> Backend contract violation: decode, annotation_decode, encode, video_output, science_output declare a disk io_role but no io_files.

### Contract

Add one field to `Node`. `Plan.describe()` already exports nodes with `asdict(n)`, so nothing else in the export path needs to change.

```python
@dataclass(frozen=True)
class DiskFile:
    path: str      # full intended path; may contain {camera}
    contents: str  # one short phrase: what the file holds

@dataclass(frozen=True)
class Node:
    ...
    io_files: tuple[DiskFile, ...] = ()
```

The viewer reads it as `node["io_files"] == [{"path": str, "contents": str}, ...]`.

| Rule | Viewer behaviour |
| --- | --- |
| `io_role` is `read` or `write` → `io_files` has ≥ 1 entry | Missing or empty: red `no path declared` folder plus the contract banner |
| `io_role == "none"` → `io_files` is empty | Ignored, but it should fail in `compile_graph` (see below) |
| `path` and `contents` are non-empty strings | Anything else throws in the viewer and shows the error banner |
| `{camera}` in `path` | Collapsed view shows the template as-is (`cam_{camera}.mp4`); camera-lane view substitutes the 1-based camera number (`cam_2.mp4`) |
| Separators | `/` and `\` are both fine. The file name is the text after the last separator |

`partition_nodes` are built with `dict(node, ...)`, so they inherit `io_files` automatically. Keep it that way.

### Validation to add in `compile_graph` (fail loudly)

Add these checks inside `visit()` next to the existing `io_role` check, raising `ValueError`:

1. `io_role in ("read", "write")` and `not n.io_files` → `"Disk node {id} declares no io_files"`
2. `io_role == "none"` and `n.io_files` → `"In-memory node {id} declares io_files"`
3. Any entry with an empty `path` or empty `contents` → `"Malformed io_files entry on {id}"`
4. `"{camera}"` in a path while `n.scope != "camera_frame"` → `"{camera} placeholder on non-camera node {id}"`
5. Duplicate `path` across all disk nodes with `io_role == "write"` → `"Two nodes save to {path}"`. A `read` and a `write` of the same path is allowed.

`io_files` takes part in `sha256(serial)` through `asdict(n)`, so changing a path changes the graph digest. That's intended: the run snapshot is tied to a definition that includes where it writes.

### Path source

These are **intended** paths: the lab still writes nothing to disk. Build them from one recording root so the viewer shows a realistic, consistent tree. Suggestion:

- Add `recording_root` to `DEFAULTS`, e.g. `"~/freemocap_data/recording_sessions/<synthetic_session>/<synthetic_recording>"`, validated as a non-empty string in `config_from`.
- Build every path from it in `definitions(c)`. Don't hard-code absolute paths per node.

If you'd rather keep config unchanged, a module-level `SYNTHETIC_RECORDING_ROOT` constant also works. The viewer doesn't care which.

### Proposed assignments (your call, these are placeholders)

| Node | `io_role` | Path (under recording root) | `contents` |
| --- | --- | --- | --- |
| `decode` | read | `synchronized_videos/cam_{camera}.mp4` | Synchronized source video for one camera |
| `annotation_decode` | read | `synchronized_videos/cam_{camera}.mp4` | Same source video, re-read for annotation |
| `encode` | write (see §2) | `annotated_videos/cam_{camera}_annotated.mp4` | Annotated video for one camera |
| `video_output` | write (see §2) | `annotated_videos/…` | Depends on the §2 decision |
| `science_output` | write | `output_data/…` (one entry per published file) | One line per file |

`science_output` currently says "no real Parquet is written". Whatever files it lists should match what the production replacement will actually publish, so the graph doubles as a spec of the output layout.

---

## 2. Graph issue: two consecutive saves in the annotation branch

`encode` (`io_role="write"`) passes `encoded_frame` in memory to `video_output` (`io_role="write"`). The viewer now draws two purple save folders back to back, which reads as "saved twice". Most likely only one of them writes the file.

Pick one:

- **A.** `encode` is in-memory encoder work (`io_role="none"`) and `video_output` is the single writer of `cam_{camera}_annotated.mp4`. Simplest story; one owner per file, matching how `science_output` is the "one publication owner".
- **B.** `encode` streams to disk (it's the writer) and `video_output` is a sealed bookkeeping step (`io_role="none"`), or writes only a manifest/index file listing the encoded videos.

The viewer renders either correctly; this is purely a graph-semantics decision. If you pick B with a manifest, give `video_output` its own `io_files` entry for the manifest path.

---

## 3. Fields the viewer depends on (don't break these)

The viewer throws on unknown enum values and missing slots instead of guessing. Renaming or removing any of these will surface as an error banner.

**`Plan.describe()`**

- Top level: `schema_version`, `digest`, `config` (incl. `frames`), `nodes`, `edges`, `partition_nodes`, `partition_edges`, `work_items`, `resources`
- `nodes[]`: `id`, `label`, `handler`, `description`, `scope`, `resource`, `ordered`, `branch`, `io_role`, `io_files`, `inputs[]` (`port`, `source`, `source_slot`, `rule`), `input_slots[]` (`name`, `data_type`, `required`), `outputs[]` (`name`, `data_type`), `partition_count`, `work_count`
- `partition_nodes[]`: all node fields plus `logical_id` and `camera`. The id is `"{node}@{camera}"`, or the plain node id when the node has no camera.
- `edges[]` / `partition_edges[]`: `id`, `source`, `target`, `source_slot`, `target_slot`, `data_type`, `rule`, `inputs_per_item`, `consumers_per_item`
- Enums the viewer knows: `io_role` ∈ {`none`, `read`, `write`}; `scope` ∈ {`recording`, `frame`, `camera_frame`}; `rule` ∈ {`same_key`, `all_sources`, `frame`, `broadcast`, `sealed`}

**Run snapshot (`/api/runs/{id}`)**

- `id`, `status`, `paused`, `elapsed_s`, `graph_digest`, `science_complete`, `resources`, `artifacts`, `retained_bytes`, `events[]` (`at`, `kind`, `node`, `detail`)
- `nodes[]` / `partition_nodes[]`: `id`, `state`, `counts`, `total`, `held`, `fail_armed`, `reasons`, `examples`, `timing` (`count`, `total_ms`, `max_ms`), `sample.payload_json`
- `state` ∈ {`pending`, `running`, `complete`, `held`, `failed`, `blocked`, `cancelled`}

Adding new enum values (a new `io_role` or `rule`, say) needs a matching viewer change. Flag it to the UX side rather than letting the viewer fall back silently; it won't.

---

## 4. Tests to add to `test_lab.py`

1. Every task variant (`mocap`, `pose`, `calibration`, with and without `annotation` and `board`): each `read`/`write` node in `describe()["nodes"]` has a non-empty `io_files`, and each `none` node has none.
2. Each of the 5 `compile_graph` validations in §1 raises on a hand-built bad `custom_nodes` graph.
3. `describe()["partition_nodes"]` entries carry the same `io_files` as their logical node.
4. No two `write` nodes declare the same path (covers the §2 fix).

---

## 5. Done when

1. `python -B -m unittest -v test_lab` passes, including the new tests.
2. With `python -B server.py --port 8766` running, the viewer shows **no red contract banner**, and every load/save folder lists file names.
3. Clicking `Scientific result`'s folder shows every file it publishes with its full path.
4. The annotation branch shows exactly one save of the annotated videos (or one video save plus one manifest save, if you pick option B).
5. Re-take the four `*-proof.jpg` screenshots so they show real file names.
6. Update the README sections on `graph.py` ownership and the HTTP surface if `recording_root` lands in config.
