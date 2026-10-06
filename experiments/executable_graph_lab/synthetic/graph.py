"""Single authored graph: compilation drives both execution and inspection."""
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from collections import Counter
from pathlib import Path, PurePosixPath, PureWindowsPath
import ntpath
from contracts import describe_contracts
from lifecycle import ResourceUse


# Intended paths only: no directories or media are created by the lab.
SYNTHETIC_RECORDING_ROOT = Path.home() / "freemocap_data" / "recording_sessions" / "graph_lab" / "synthetic_recording"


# Application concepts, not assertions that the synthetic JSON payloads implement
# these production Python classes. Bindings and outputs use the same vocabulary.
DATA_TYPES = {
    'recording': 'recording_context', 'image': 'video_frame',
    'board': 'charuco_observation', 'pose': 'keypoint_observations_2d',
    'observations': 'camera_observations', 'geometry': 'camera_models',
    'raw_3d': 'raw_keypoints_3d', 'trajectory': 'prepared_keypoint_trajectories',
    'scale': 'recording_scale_fit', 'skeleton': 'skeleton_reconstruction',
    'result': 'publication_receipt', 'annotated_image': 'annotation_frame',
    'encoded_frame': 'encoded_frame_receipt',
    'timing': 'recording_timing', 'detector_config': 'detector_configuration',
    'session': 'inference_session', 'board_definition': 'charuco_board_definition',
    'calibration': 'calibration_document', 'publication': 'publication_plan',
}

# Paths relative to the FreeMoCap checkout. References identify implementation
# candidates, not imported adapters. The viewer still consumes one graph.
APP_REFERENCES = {
    'timing': ('freemocap/core/reconstruction/recording_timing.py:RecordingGroupTiming',),
    'detector_config': ('freemocap/core/tracking/tracker_factory.py:tracker_session_requests',),
    'session': ('freemocap/core/pipeline/inference_service.py:InferenceService',),
    'board_definition': ('freemocap/core/pipeline/posthoc/mocap_detection.py:detect_mocap_recording',),
    'calibration_load': ('freemocap/core/tasks/mocap/posthoc_mocap_task.py:run_posthoc_mocap_task',),
    'publication': ('freemocap/core/recording/result_processing/observation_publication.py:publish_posthoc_observations',),
    'recording': ('freemocap/core/pipeline/posthoc/video_group_helper.py:VideoGroupHelper',),
    'decode': ('freemocap/core/pipeline/posthoc/mocap_video_node.py:ReadFrame',),
    'board': ('freemocap/core/pipeline/posthoc/mocap_video_node.py:MocapVideoNode',),
    'pose': ('freemocap/core/pipeline/inference_service.py:InferenceService',),
    'observations': ('freemocap/core/pipeline/posthoc/mocap_detection.py:MocapDetectionFrame',),
    'geometry': ('freemocap/core/tasks/mocap/posthoc_mocap_task.py:run_posthoc_mocap_task',),
    'triangulate': ('freemocap/core/reconstruction/posthoc_reconstruction.py:triangulate_observation_buffers',),
    'filter': ('freemocap/core/reconstruction/posthoc_filtering.py:prepare_recording_points',),
    'scale': ('freemocap/core/reconstruction/posthoc_reconstruction.py:reconstruct_skeletons_for_recording',),
    'reconstruct': ('freemocap/core/skeletons/reconstruct_skeleton.py:reconstruct_skeleton',
                    'freemocap/core/skeletons/skeleton_reconstruction.py:SkeletonReconstruction'),
    'calibrate': ('freemocap/core/tasks/calibration/posthoc_calibration_task.py:run_posthoc_calibration_task',),
    'science_output': ('freemocap/core/recording/result_processing/observation_publication.py:publish_posthoc_observations',),
    'annotation_decode': ('freemocap/core/pipeline/posthoc/annotation_output.py:AnnotationVideoOutput',),
    'draw': ('freemocap/core/pipeline/posthoc/annotation_style.py:build_observation_annotator',),
    'encode': ('freemocap/core/pipeline/posthoc/annotation_output.py:AnnotationVideoOutput',),
    'video_output': ('freemocap/core/pipeline/posthoc/mocap_video_node.py:FinishVideo',),
}


TASKS = [
    {"id": "mocap", "label": "Motion capture", "description": "Posthoc observations, triangulation, trajectory preparation and skeleton reconstruction (simulated)."},
    {"id": "pose", "label": "Pose tracking", "description": "Posthoc 2D tracking and observation checkpoint publication (simulated)."},
    {"id": "calibration", "label": "Camera calibration", "description": "ChArUco detection and camera calibration (simulated)."},
]
DEFAULTS = dict(task="mocap", cameras=3, frames=30, annotation=True, board=True,
                cpu_slots=3, io_slots=3, gpu_slots=1, encoder_slots=2,
                compute_ms=35, annotation_ms=120)


def config_from(raw):
    if not isinstance(raw, dict) or set(raw) - set(DEFAULTS):
        raise ValueError("Unknown configuration fields")
    c = DEFAULTS | raw
    if c["task"] not in {t["id"] for t in TASKS}:
        raise ValueError("Unknown task")
    for key, low, high in [("cameras", 1, 4), ("frames", 2, 120), ("cpu_slots", 1, 8),
                           ("io_slots", 1, 8), ("gpu_slots", 1, 1), ("encoder_slots", 1, 4),
                           ("compute_ms", 0, 500), ("annotation_ms", 0, 1000)]:
        if type(c[key]) is not int or not low <= c[key] <= high:
            raise ValueError(f"{key} must be an integer from {low} to {high}")
    for key in ("annotation", "board"):
        if type(c[key]) is not bool:
            raise ValueError(f"{key} must be boolean")
    return c


@dataclass(frozen=True)
class InputSlot:
    name: str
    data_type: str
    required: bool = True


@dataclass(frozen=True)
class OutputSlot:
    name: str
    data_type: str


@dataclass(frozen=True)
class Binding:
    port: str
    source: str
    data_type: str
    rule: str  # broadcast, same_key, all_sources, frame, sealed
    source_slot: str = "out"


@dataclass(frozen=True)
class DiskFile:
    path: str
    contents: str


@dataclass(frozen=True)
class Node:
    id: str
    label: str
    handler: str
    scope: str  # recording, frame, camera_frame
    resource: str
    outputs: tuple[OutputSlot, ...]
    inputs: tuple[Binding, ...] = ()
    ordered: bool = False
    branch: str = "science"
    description: str = ""
    io_role: str = "none"  # Intended adapter effect; all handlers remain synthetic.
    input_slots: tuple[InputSlot, ...] = ()
    io_files: tuple[DiskFile, ...] = ()
    source_refs: tuple[str, ...] = ()
    resource_uses: tuple[ResourceUse, ...] = ()


@dataclass(frozen=True)
class Work:
    id: str
    node: str
    frame: int | None
    camera: int | None
    inputs: tuple[tuple[str, tuple[str, ...]], ...]
    predecessor: str | None


@dataclass(frozen=True)
class Plan:
    config: dict
    nodes: tuple[Node, ...]
    work: tuple[Work, ...]
    digest: str

    def describe(self):
        nodes = [asdict(n) for n in self.nodes]
        work_by_id = {w.id: w for w in self.work}
        def partition(w):
            return f"{w.node}@{w.camera}" if w.camera is not None else w.node
        partitions = []
        for node in nodes:
            works = [w for w in self.work if w.node == node["id"]]
            cameras = sorted({w.camera for w in works if w.camera is not None})
            node["partition_count"] = len(cameras) or 1
            node["work_count"] = len(works)
            for camera in cameras or [None]:
                partitions.append(dict(node, id=f"{node['id']}@{camera}" if camera is not None else node["id"],
                                       logical_id=node["id"], camera=camera,
                                       label=f"{node['label']} · C{camera + 1}" if camera is not None else node["label"]))
        edges = [dict(id=f"{n.id}:{b.port}", source=b.source, target=n.id,
                      port=b.port, source_slot=b.source_slot, target_slot=b.port, data_type=b.data_type, rule=b.rule)
                 for n in self.nodes for b in n.inputs]
        partition_edges = []
        for edge in edges:
            links = [(source, w.id) for w in self.work if w.node == edge["target"]
                     for port, sources in w.inputs if port == edge["port"] for source in sources]
            consumers = Counter(source for source, _ in links)
            producers = Counter(target for _, target in links)
            edge.update(inputs_per_item=max(producers.values(), default=0),
                        consumers_per_item=max(consumers.values(), default=0))
            edge["fan"] = "fan-in" if edge["inputs_per_item"] > 1 else "fan-out" if edge["consumers_per_item"] > 1 else "one-to-one"
            pairs = sorted({(partition(work_by_id[s]), partition(work_by_id[t])) for s, t in links})
            for source, target in pairs:
                partition_edges.append(dict(edge, id=f"{edge['id']}:{source}:{target}", source=source, target=target))
        return dict(schema_version=3, digest=self.digest, config=dict(self.config), nodes=nodes,
                    contracts=describe_contracts({s.data_type for n in self.nodes for s in (*n.input_slots, *n.outputs)}),
                    partition_nodes=partitions, partition_edges=partition_edges,
                    edges=edges, work_items=len(self.work), synthetic=True,
                    resources={name: self.config[f"{name}_slots"] for name in ("cpu", "io", "gpu", "encoder")})


def definitions(c):
    nodes = []
    root = SYNTHETIC_RECORDING_ROOT
    def disk(relative, contents):
        return DiskFile((root / relative).as_posix(), contents)
    source_video = disk("videos/synchronized/cam_{camera}.mp4", "Synchronized source video for one camera")
    science_file = (disk(f"{root.name}_calibration.toml", "Solved camera geometry") if c['task'] == 'calibration'
                    else disk(f"{root.name}_data.parquet", "Reconstructed skeleton samples and embedded recording metadata" if c['task'] == 'mocap' else "Tracked observations and embedded recording metadata"))
    def add(id, label, handler, scope, resource, output, inputs=(), ordered=False, branch="science", description="", io_role="none", optional_slots=(), io_files=()):
        slots = tuple(InputSlot(b.port, b.data_type) for b in inputs if b.port not in {s.name for s in optional_slots}) + tuple(optional_slots)
        refs = APP_REFERENCES.get(id, ())
        if id == 'science_output' and c['task'] == 'calibration':
            refs = ('freemocap/core/tasks/calibration/posthoc_calibration_task.py:_save_result',)
        uses = ((ResourceUse('inference_session', 'recording'),) if id in ('session', 'pose') else
                (ResourceUse('annotation_writer', 'camera'),) if id == 'encode' else ())
        nodes.append(Node(id, label, handler, scope, resource, (OutputSlot("out", DATA_TYPES[output]),), tuple(inputs), ordered, branch, description, io_role, slots, tuple(io_files), refs, uses))
    def bind(port, source, kind, rule):
        return Binding(port, source, DATA_TYPES[kind], rule)
    add("recording", "Recording context", "recording", "recording", "io", "recording",
        description="Models VideoGroupHelper metadata and recording identity. Synthetic camera IDs and frame counts; no manifest or video is read.")
    add('timing', 'Resolve recording timing', 'timing', 'recording', 'cpu', 'timing',
        [bind('recording', 'recording', 'recording', 'broadcast')],
        description='Models RecordingGroupTiming.resolve. Publishes camera IDs, frame numbers and synchronized timestamps. The lab validates a synthetic 30 Hz grid; production must resolve recorded timing and fallback provenance.')
    add('publication', 'Plan artifact publication', 'publication_plan', 'recording', 'cpu', 'publication',
        [bind('recording', 'recording', 'recording', 'broadcast')],
        description='Proposed run-scoped publication contract: recording identity, completed-stage provenance and durable-versus-simulated receipt semantics. No files are opened. Actual atomic publication and rollback remain adapter responsibilities.')
    add("decode", "Decode synchronized video", "decode", "camera_frame", "io", "image",
        [bind("recording", "recording", "recording", "broadcast"), bind('timing', 'timing', 'timing', 'broadcast')], True,
        description="Maps to ReadFrame in MocapVideoNode: ordered decoding per camera. This handler emits frame descriptors, not decoded pixel arrays.", io_role="read", io_files=(source_video,))
    if c["task"] == "calibration" or c["board"]:
        add('board_definition', 'Select ChArUco board', 'board_definition', 'recording', 'cpu', 'board_definition',
            description='Explicit board definition for this fixture. Production automatic board selection requires observation evidence and is not represented by this explicit-selection variant.')
        add("board", "Detect ChArUco corners", "board", "camera_frame", "cpu", "board",
            [bind("image", "decode", "image", "same_key"), bind('definition', 'board_definition', 'board_definition', 'broadcast')], True,
            description="Independent ChArUco observation producer with a required explicit board definition. Maps to work currently inside MocapVideoNode annotation handling. Simulated corners only.")
    if c["task"] != "calibration":
        add('detector_config', 'Configure pose detector', 'detector_config', 'recording', 'cpu', 'detector_config',
            description='RTMPose family, pose/person model references and requested CUDA provider. These are fixture identifiers, not downloaded model assets. Provider policy requires a real adapter to verify CUDA rather than silently fall back.')
        add('session', 'Open inference session', 'session', 'recording', 'gpu', 'session',
            [bind('config', 'detector_config', 'detector_config', 'broadcast'), bind('timing', 'timing', 'timing', 'broadcast')],
            description='Models InferenceService registration and tracker_session_requests with camera batch size. Emits an immutable session descriptor; live handles belong to the executor resource owner. Provider is explicitly simulated. Cleanup must run on completion, failure and cancellation.')
        add("pose", "RTMPose camera batch", "pose", "frame", "gpu", "pose",
            [bind("images", "decode", "image", "all_sources"), bind('session', 'session', 'session', 'broadcast')], True,
            description="Maps to InferenceService and tracker_session_requests: one synchronized camera batch using the configured RTMPose/RTMW weights and person detector. CUDA is a target, not a measured provider here; no detector runs.")
        inputs = [bind("poses", "pose", "pose", "same_key")]
        if c["board"]:
            inputs.append(bind("boards", "board", "board", "all_sources"))
        add("observations", "Assemble camera observations", "observations", "frame", "cpu", "observations", inputs,
            description="Models MocapDetectionFrame.observations keyed by camera. Combines keypoint and optional ChArUco observations for one frame. A connected optional input is awaited. Observation payloads remain synthetic.",
            optional_slots=(InputSlot("boards", DATA_TYPES["board"], False),))
        if c["task"] == "mocap":
            if c['cameras'] > 1:
                add('calibration_load', 'Load selected calibration', 'calibration_load', 'recording', 'io', 'calibration',
                    [bind('recording', 'recording', 'recording', 'broadcast')],
                    description='Models CalibrationResult.load_toml with file-identity validation. Explicit synthetic selection; no TOML is read. Camera matching must succeed before triangulation.', io_role='read',
                    io_files=(disk('selected_calibration.toml', 'Explicitly selected calibration fixture'),))
            geometry_inputs = [bind('recording', 'recording', 'recording', 'broadcast')]
            if c['cameras'] > 1:
                geometry_inputs += [bind('calibration', 'calibration_load', 'calibration', 'broadcast'), bind('evidence', 'observations', 'observations', 'sealed')]
            add("geometry", "Resolved camera models", "geometry", "recording", "cpu", "geometry",
                geometry_inputs,
                description="Multicamera: resolve calibration camera assignments from sealed observation evidence, matching the current PosthocMatchingRequest boundary. This deliberately gates triangulation until matching completes. Single camera: explicit planar fallback, no calibration read. Geometry remains synthetic.")
            add("triangulate", "Triangulate keypoints", "triangulate", "frame", "cpu", "raw_3d",
                [bind("observations", "observations", "observations", "same_key"), bind("geometry", "geometry", "geometry", "broadcast")],
                description="Maps to triangulate_observation_buffers and RAW_KEYPOINTS_3D. Per-frame scheduling is proposed; production currently processes accumulated buffers. Reprojection diagnostics and weights are not modeled by this synthetic transform.")
            add("filter", "Prepare 3D trajectories", "filter", "recording", "cpu", "trajectory",
                [bind("points", "triangulate", "raw_3d", "sealed"), bind('timing', 'timing', 'timing', 'broadcast')],
                description="Maps to prepare_recording_points: trajectory gap filling followed by timestamp-aware Butterworth filtering. Prepared coordinates and measured-support provenance must remain distinct. Lab uses an identity operation over a sealed recording.")
            add("scale", "Fit recording-wide model scale", "scale", "recording", "cpu", "scale",
                [bind("trajectory", "filter", "trajectory", "broadcast")],
                description="Maps to recording-wide scale fitting in reconstruct_skeletons_for_recording and FittedRecordingScale. Requires model definitions and measured-support evidence, not only coordinates. Lab fixes scale to 1.0; those inputs are not yet modeled.")
            add("reconstruct", "Reconstruct anchored skeleton", "reconstruct", "frame", "cpu", "skeleton",
                [bind("trajectory", "filter", "trajectory", "broadcast"), bind("scale", "scale", "scale", "broadcast")], True,
                description="Maps to reconstruct_skeleton with FrozenModelScale and anchored synthesis. Production keeps mapped_keypoints, rigid landmarks, segment origins and rotations distinct. Lab returns a toy root/scale descriptor, not SkeletonReconstruction.")
            scientific = ("reconstruct", "skeleton")
        else:
            scientific = ("observations", "observations")
        annotation_input = bind("observations", "observations", "observations", "frame")
    else:
        add("calibrate", "Solve ChArUco calibration", "calibrate", "recording", "cpu", "geometry",
            [bind("boards", "board", "board", "sealed"), bind('definition', 'board_definition', 'board_definition', 'broadcast'), bind('timing', 'timing', 'timing', 'broadcast')],
            description="Maps to run_posthoc_calibration_task using selected ChArUco observations and video metadata. Board selection, intrinsics/extrinsics solving and validation are not implemented in the simulation.")
        scientific = ("calibrate", "geometry")
        annotation_input = bind("observations", "board", "board", "same_key")
    add("science_output", "Publish processing checkpoint", "publish", "recording", "io", "result",
        [bind("data", *scientific, "sealed"), bind('plan', 'publication', 'publication', 'broadcast'), bind('timing', 'timing', 'timing', 'broadcast')],
        description="Represents Parquet checkpoint publication via publish_posthoc_observations. Production publishes several completed stages with provenance, not just this final sink. The lab declares one intended file and returns a simulated receipt.", io_role="write", io_files=(science_file,))
    if c["annotation"]:
        add("annotation_decode", "Decode annotation source", "decode", "camera_frame", "io", "image",
            [bind("recording", "recording", "recording", "broadcast"), bind('timing', 'timing', 'timing', 'broadcast')], True, "annotation",
            "Proposed independent source-video decoding for AnnotationVideoOutput. Current MocapVideoNode reuses inference images; decoupled read scheduling is part of the replacement, not current app behavior.", io_role="read", io_files=(source_video,))
        add("draw", "Render observation overlays", "draw", "camera_frame", "cpu", "annotated_image",
            [bind("image", "annotation_decode", "image", "same_key"), annotation_input], False, "annotation",
            description="Maps to build_observation_annotator and AnnotationVideoOutput.write_frame. Draws tracker and ChArUco overlays; does not generate scientific observations. Separate rendering is a proposed boundary; lab emits a frame descriptor.")
        add("encode", "Write annotated video", "encode", "camera_frame", "encoder", "encoded_frame",
            [bind("image", "draw", "annotated_image", "same_key"), bind('plan', 'publication', 'publication', 'broadcast'), bind('timing', 'timing', 'timing', 'broadcast')], True, "annotation",
            "One ordered writer per camera. Last-frame work includes close and publication before its completion receipt is emitted. Cancellation/failure cleanup belongs to the resource owner. All writes, closes and publications here are simulated.", io_role="write",
            io_files=(disk("videos/annotated/cam_{camera}.mp4.annotated.mp4", "Annotated video for one camera"),))
        add("video_output", "Collect video completion receipts", "publish", "recording", "io", "result",
            [bind("frames", "encode", "encoded_frame", "sealed"), bind('plan', 'publication', 'publication', 'broadcast'), bind('timing', 'timing', 'timing', 'broadcast')], False, "annotation",
            description="Validates every expected camera/frame receipt and one closed/published stream receipt per camera before reporting completion. Simulated publication is explicitly non-durable. No second writer and no dependency from science.")
    if c['task'] == 'calibration':
        from dataclasses import replace
        nodes = [replace(n, label='Publish calibration TOML', description='Maps to _save_result and CalibrationResult TOML serialization. Intended output only; calibration solving and file publication remain simulated.') if n.id == 'science_output' else n for n in nodes]
    return tuple(nodes)


def compile_graph(raw, custom_nodes=None):
    c = config_from(raw)
    nodes = definitions(c) if custom_nodes is None else tuple(custom_nodes)
    by_id = {n.id: n for n in nodes}
    if len(by_id) != len(nodes):
        raise ValueError("Duplicate node identity")
    depths = {}
    writers = {}
    def visit(id, stack):
        if id in stack:
            raise ValueError("Dependency cycle")
        if id in depths:
            return depths[id]
        n = by_id[id]
        for use in n.resource_uses:
            if not use.name or use.scope not in ('recording', 'camera') or (use.scope == 'camera' and n.scope != 'camera_frame'):
                raise ValueError('Invalid resource lifetime declaration')
        if n.io_role not in ("none", "read", "write"):
            raise ValueError("Invalid I/O role")
        if n.io_role in ("read", "write") and not n.io_files:
            raise ValueError(f"Disk node {id} declares no io_files")
        if n.io_role == "none" and n.io_files:
            raise ValueError(f"In-memory node {id} declares io_files")
        for entry in n.io_files:
            if (not isinstance(entry, DiskFile) or not isinstance(entry.path, str) or not entry.path.strip()
                    or not isinstance(entry.contents, str) or not entry.contents.strip()):
                raise ValueError(f"Malformed io_files entry on {id}")
            if '{camera}' in entry.path and n.scope != 'camera_frame':
                raise ValueError(f"{{camera}} placeholder on non-camera node {id}")
            remainder = entry.path.replace('{camera}', '1')
            if ('{' in remainder or '}' in remainder or '\x00' in remainder
                    or not (PureWindowsPath(remainder).is_absolute() or PurePosixPath(remainder).is_absolute())):
                raise ValueError(f"Malformed io_files entry on {id}: expected an absolute path with only {{camera}} placeholders")
            if n.io_role == 'write':
                paths = [entry.path.replace('{camera}', str(camera + 1)) for camera in range(c['cameras'])] if '{camera}' in entry.path else [entry.path]
                for path in paths:
                    # Canonicalize Windows aliases and template/literal collisions.
                    key = ntpath.normcase(ntpath.normpath(path)) if PureWindowsPath(path).is_absolute() else str(PurePosixPath(path))
                    if key in writers:
                        raise ValueError(f"Two nodes save to {path}")
                    writers[key] = id
        if n.scope not in ("recording", "frame", "camera_frame") or n.resource not in ("cpu", "io", "gpu", "encoder"):
            raise ValueError("Invalid scope or resource")
        if len({b.port for b in n.inputs}) != len(n.inputs):
            raise ValueError("Duplicate input port")
        slots = {s.name: s for s in n.input_slots}
        outputs = {s.name: s for s in n.outputs}
        if len(slots) != len(n.input_slots) or len(outputs) != len(n.outputs):
            raise ValueError("Duplicate slot name")
        if not outputs or any(not s.name or not s.data_type for s in (*n.input_slots, *n.outputs)):
            raise ValueError("Invalid slot declaration")
        if any(s.required and s.name not in {b.port for b in n.inputs} for s in n.input_slots):
            raise ValueError("Required input slot is unconnected")
        for b in n.inputs:
            producer = by_id.get(b.source)
            output = next((s for s in producer.outputs if s.name == b.source_slot), None) if producer else None
            if b.port not in slots or not output or output.data_type != slots[b.port].data_type or b.data_type != slots[b.port].data_type:
                raise ValueError("Unknown producer or incompatible port type")
        depths[id] = 1 + max((visit(b.source, stack | {id}) for b in n.inputs), default=-1)
        return depths[id]
    for n in nodes:
        visit(n.id, set())
    ordered = sorted(nodes, key=lambda n: depths[n.id])
    keys = {}
    works = []
    def identity(id, f, cam):
        return f"{id}/{f if f is not None else 'all'}/{cam if cam is not None else 'all'}"
    for n in ordered:
        keys[n.id] = [(None, None)] if n.scope == "recording" else [
            (f, cam) for f in range(c["frames"])
            for cam in (range(c["cameras"]) if n.scope == "camera_frame" else [None])]
        for f, cam in keys[n.id]:
            inputs = []
            for b in n.inputs:
                scope = by_id[b.source].scope
                if b.rule == "broadcast" and scope == "recording":
                    selected = [(None, None)]
                elif b.rule == "same_key" and scope == n.scope:
                    selected = [(f, cam)]
                elif b.rule == "all_sources" and scope == "camera_frame" and n.scope == "frame":
                    selected = [(f, k) for k in range(c["cameras"])]
                elif b.rule == "frame" and scope == "frame" and n.scope == "camera_frame":
                    selected = [(f, None)]
                elif b.rule == "sealed" and n.scope == "recording":
                    selected = keys[b.source]
                else:
                    raise ValueError(f"Incompatible key binding: {n.id}.{b.port}")
                inputs.append((b.port, tuple(identity(b.source, a, z) for a, z in selected)))
            predecessor = identity(n.id, f - 1, cam) if n.ordered and f is not None and f > 0 else None
            works.append(Work(identity(n.id, f, cam), n.id, f, cam, tuple(inputs), predecessor))
    if len(works) > 5000:
        raise ValueError("Synthetic work budget exceeded")
    serial = json.dumps(dict(config=c, nodes=[asdict(n) for n in nodes],
        contracts=describe_contracts({s.data_type for n in nodes for s in (*n.input_slots, *n.outputs)})), sort_keys=True)
    return Plan(c, tuple(ordered), tuple(works), sha256(serial.encode()).hexdigest()[:16])
