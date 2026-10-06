"""Event-driven keyed DAG executor. Handlers receive data, never other tasks' futures."""
import asyncio
from collections import Counter, deque
from dataclasses import asdict, dataclass
import json
import math
from threading import RLock, Thread
from time import monotonic
from uuid import uuid4

from graph import compile_graph
from contracts import validate_payload
from lifecycle import ResourceOwner


@dataclass(frozen=True)
class Artifact:
    data_type: str
    work_id: str
    payload_json: str  # Immutable by construction; handlers deserialize their own values.


def validate_timing(timing):
    frames, cameras, timestamps = timing['frame_numbers'], timing['camera_ids'], timing['timestamps_s']
    if (not frames or frames != list(range(len(frames))) or not cameras
            or len(set(cameras)) != len(cameras) or len(timestamps) != len(frames)
            or any(not isinstance(t, (int, float)) or not math.isfinite(t) for t in timestamps)
            or any(b <= a for a, b in zip(timestamps, timestamps[1:]))):
        raise ValueError('Invalid synchronized recording timing')


def validate_video_receipts(receipts, timing):
    validate_timing(timing)
    expected = {(c, f) for c in timing['camera_ids'] for f in timing['frame_numbers']}
    actual = [(r['camera'], r['frame']) for r in receipts]
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError('Missing or duplicate video frame receipts')
    last = timing['frame_numbers'][-1]
    if any(r.get('stream_closed') != (r['frame'] == last)
           or r.get('publication') != ('simulated' if r['frame'] == last else 'pending')
           or r.get('durable') is not False for r in receipts):
        raise ValueError('Video stream has no valid close/publication receipt')


async def execute(node, work, inputs, config):
    """Synthetic cost and values; no I/O, GPU, model, or production algorithms."""
    cost = config["annotation_ms"] if node.handler == "encode" else config["compute_ms"]
    factor = {"recording": .1, "decode": .3, "observations": .08, "geometry": .2,
              "draw": .3, "publish": 1, "filter": 2, "scale": 1.5}.get(node.handler, 1)
    await asyncio.sleep(cost * factor / 1000)
    data = {k: [json.loads(a.payload_json) for a in values] for k, values in inputs.items()}
    f, cam = work.frame, work.camera
    match node.handler:
        case "recording":
            result = dict(recording_id='synthetic_recording', frames=config["frames"], cameras=config["cameras"], fps=30, seed=0)
        case 'timing':
            recording = data['recording'][0]
            result = dict(camera_ids=list(range(recording['cameras'])), frame_numbers=list(range(recording['frames'])),
                          timestamps_s=[i / recording['fps'] for i in range(recording['frames'])], provenance='synthetic uniform grid')
            validate_timing(result)
        case 'publication_plan':
            result = dict(recording_id=data['recording'][0]['recording_id'], task=config['task'], mode='simulated', durable=False)
        case 'detector_config':
            result = dict(family='RTMPose', pose_model='fixture:pose', person_model='fixture:person',
                          requested_provider='CUDAExecutionProvider', allow_cpu_fallback=False)
        case 'session':
            validate_timing(data['timing'][0])
            result = dict(session_id=work.id, configuration=data['config'][0],
                          camera_ids=data['timing'][0]['camera_ids'], actual_provider='simulated', live_handle=False)
        case 'board_definition':
            result = dict(board_id='fixture:charuco', selection='explicit', synthetic=True)
        case 'calibration_load':
            result = dict(camera_ids=list(range(data['recording'][0]['cameras'])), file=node.io_files[0].path,
                          identity='synthetic fixture; no file hash', synthetic=True)
        case "decode":
            timing = data['timing'][0]
            validate_timing(timing)
            if cam not in timing['camera_ids']: raise ValueError('Unknown camera')
            result = dict(frame=f, camera=cam, timestamp=timing['timestamps_s'][f], synthetic_image=True)
        case "pose":
            session = data['session'][0]
            if (sorted(x['camera'] for x in data['images']) != session['camera_ids']
                    or any(x['frame'] != f for x in data['images'])
                    or len({x['timestamp'] for x in data['images']}) != 1):
                raise ValueError('Inference batch does not match session cameras or synchronized frame')
            result = dict(frame=f, poses=[dict(camera=x["camera"], x=round(math.sin(f / 9) + x["camera"] * .1, 4),
                                              y=round(math.cos(f / 9), 4)) for x in data["images"]], batch_size=len(data["images"]),
                          session_id=session['session_id'], provider=session['actual_provider'])
        case "board":
            result = dict(frame=f, camera=cam, corners=12, board_id=data['definition'][0]['board_id'])
        case "observations":
            result = dict(frame=f, poses=data["poses"][0]["poses"], boards=len(data.get("boards", [])))
        case "geometry":
            if config['cameras'] > 1 and data['calibration'][0]['camera_ids'] != list(range(config['cameras'])):
                raise ValueError('Calibration camera assignment mismatch')
            result = dict(cameras=config["cameras"], source='synthetic camera matching' if config['cameras'] > 1 else 'single-camera planar fallback',
                          evidence_frames=len(data.get('evidence', [])))
        case "triangulate":
            poses = data["observations"][0]["poses"]
            result = dict(frame=f, xyz=[round(sum(p["x"] for p in poses)/len(poses), 4), poses[0]["y"], 1.0])
        case "filter":
            validate_timing(data['timing'][0])
            result = dict(points=data["points"], timestamps_s=data['timing'][0]['timestamps_s'], algorithm="synthetic identity filter; sealed-input contract only")
        case "scale":
            result = dict(scale=1.0, evidence_frames=len(data["trajectory"][0]["points"]))
        case "reconstruct":
            result = dict(frame=f, root=data["trajectory"][0]["points"][f]["xyz"], scale=data["scale"][0]["scale"])
        case "calibrate":
            result = dict(cameras=len(data['timing'][0]['camera_ids']), board_id=data['definition'][0]['board_id'], board_samples=len(data["boards"]), geometry="synthetic")
        case "draw":
            result = dict(frame=f, camera=cam, observations_ready=True)
        case "encode":
            closed = f == data['timing'][0]['frame_numbers'][-1]
            result = dict(frame=f, camera=cam, encoded=True, stream_closed=closed,
                          publication='simulated' if closed else 'pending', durable=False,
                          recording_id=data['plan'][0]['recording_id'])
        case "publish":
            if node.id == 'video_output':
                validate_video_receipts(data['frames'], data['timing'][0])
            result = dict(items=len(data.get('frames', data.get('data', []))), synthetic=True, publication='simulated', durable=False,
                          recording_id=data['plan'][0]['recording_id'], stage=node.id,
                          provenance={port: [a.work_id for a in values] for port, values in inputs.items()})
        case _:
            raise ValueError(f"Unregistered handler: {node.handler}")
    return {"out": Artifact(node.outputs[0].data_type, work.id, json.dumps(result, sort_keys=True))}


def validate_outputs(node, work, outputs):
    declared = {slot.name: slot.data_type for slot in node.outputs}
    if set(outputs) != set(declared):
        raise ValueError("Handler outputs do not match declared output slots")
    if any(a.data_type != declared[name] or a.work_id != work.id for name, a in outputs.items()):
        raise ValueError("Handler output type or work identity mismatch")
    for artifact in outputs.values():
        validate_payload(artifact.data_type, json.loads(artifact.payload_json))


class Run:
    def __init__(self, config, held=(), paused=False, resource_factory=None):
        self.plan = compile_graph(config)
        self.id = str(uuid4())
        self.nodes = {n.id: n for n in self.plan.nodes}
        if set(held) - self.nodes.keys():
            raise ValueError("Unknown held node")
        self.lock = RLock()
        self.states = {w.id: "pending" for w in self.plan.work}
        self.artifacts = {}
        self.retained_bytes = 0
        self.max_bytes = 8 * 1024 * 1024
        self.held = set(held)
        self.fail_next = set()
        self.paused, self.cancelled, self.steps = paused, False, 0
        self.status = "created"
        self.revision = 0
        self.started = monotonic()
        self.finished = None
        self.active = Counter()
        self.timing = {n.id: dict(count=0, total_ms=0.0, max_ms=0.0) for n in self.plan.nodes}
        self.events = deque(maxlen=120)
        self.loop = None
        self.wakeup = None
        self.thread = None
        self.owner = ResourceOwner(self.plan, self.event, resource_factory)
        self.tasks = set()

    def event(self, kind, node=None, detail=""):
        self.revision += 1
        self.events.append(dict(sequence=self.revision, at=round(monotonic()-self.started, 3),
                                kind=kind, node=node, detail=detail))

    def start(self):
        self.thread = Thread(target=lambda: asyncio.run(self.run()), daemon=True, name=f"GraphLab-{self.id[:8]}")
        self.thread.start()

    def command(self, action, node=None):
        with self.lock:
            if self.status in ("complete", "partial", "failed", "cancelled"):
                raise ValueError("Run is terminal; create a new run")
            if action in ("hold", "release", "fail") and node not in self.nodes:
                raise ValueError("Select an existing node")
            if action == "pause": self.paused = True
            elif action == "resume": self.paused, self.steps = False, 0
            elif action == "step": self.paused, self.steps = True, self.steps + 1
            elif action == "cancel": self.cancelled = True
            elif action == "hold": self.held.add(node)
            elif action == "release": self.held.discard(node)
            elif action == "fail": self.fail_next.add(node)
            else: raise ValueError("Unknown command")
            self.event(action, node, "Applies to new dispatches; running work may finish.")
            if self.loop and self.wakeup:
                self.loop.call_soon_threadsafe(self.wakeup.set)

    def dependencies(self, w):
        return [key for _, keys in w.inputs for key in keys]

    def reason(self, w):
        deps = self.dependencies(w)
        if any(self.states[d] in ("failed", "blocked", "cancelled") for d in deps):
            return "upstream failure", [d for d in deps if self.states[d] in ("failed", "blocked", "cancelled")][:4]
        if w.predecessor and self.states[w.predecessor] in ("failed", "blocked", "cancelled"):
            return "ordering predecessor failed", [w.predecessor]
        missing = [d for d in deps if self.states[d] != "complete"]
        if missing: return "waiting for input", missing[:4]
        if w.predecessor and self.states[w.predecessor] != "complete":
            return "waiting for ordering", [w.predecessor]
        if w.node in self.held: return "held by user", []
        if self.paused and self.steps == 0: return "paused", []
        resource = self.nodes[w.node].resource
        if self.active[resource] >= self.plan.config[f"{resource}_slots"]:
            return "waiting for resource", [resource]
        return "ready", []

    async def invoke(self, w):
        n = self.nodes[w.node]
        start = monotonic()
        try:
            with self.lock:
                fail = w.node in self.fail_next
                self.fail_next.discard(w.node)
                bindings = {b.port: b for b in n.inputs}
                inputs = {port: tuple(self.artifacts[d][bindings[port].source_slot] for d in deps) for port, deps in w.inputs}
                for slot in n.input_slots:
                    inputs.setdefault(slot.name, ())
                for values in inputs.values():
                    for artifact in values:
                        validate_payload(artifact.data_type, json.loads(artifact.payload_json))
                self.owner.acquire(n, w)
            if fail:
                raise RuntimeError("Injected synthetic failure")
            outputs = await execute(n, w, inputs, self.plan.config)
            if n.handler == 'encode' and w.frame == self.plan.config['frames'] - 1:
                # A receipt cannot claim stream closure until the owner confirms it.
                await self.owner.finish(n, w)
            validate_outputs(n, w, outputs)
            with self.lock:
                if self.cancelled:
                    self.states[w.id] = "cancelled"
                else:
                    size = sum(len(a.payload_json.encode()) for a in outputs.values())
                    if self.retained_bytes + size > self.max_bytes:
                        raise RuntimeError("Synthetic artifact memory budget exhausted")
                    self.artifacts[w.id] = outputs
                    self.retained_bytes += size
                    self.states[w.id] = "complete"
                    self.event("completed", n.id, w.id)
        except asyncio.CancelledError:
            with self.lock: self.states[w.id] = "cancelled"
        except Exception as error:
            with self.lock:
                self.states[w.id] = "failed"
                self.event("failed", n.id, str(error))
        finally:
            with self.lock:
                self.active[n.resource] -= 1
                ms = (monotonic()-start)*1000
                t = self.timing[n.id]
                t["count"] += 1
                t["total_ms"] += ms
                t["max_ms"] = max(t["max_ms"], ms)
            self.wakeup.set()

    async def run(self):
        outcome = 'failed'
        try:
            outcome = await self.schedule()
        except Exception as error:
            with self.lock:
                self.event('scheduler_failed', detail=str(error))
        finally:
            # Never report a terminal run while a handler or cleanup is live.
            for task in tuple(self.tasks): task.cancel()
            if self.tasks: await asyncio.gather(*tuple(self.tasks), return_exceptions=True)
            await self.owner.close_all()
            with self.lock:
                for key, record in self.owner.records.items():
                    if record['error']:
                        if 'science' in self.owner.branches[key]: outcome = 'failed'
                        elif outcome == 'complete': outcome = 'partial'
                self.status = outcome
                self.finished = monotonic()
                self.event(outcome)

    async def schedule(self):
        self.loop, self.wakeup = asyncio.get_running_loop(), asyncio.Event()
        active_tasks = self.tasks
        with self.lock:
            self.status = "running"
            self.event("started", detail=self.plan.digest)
        while True:
            self.wakeup.clear()
            with self.lock:
                if self.cancelled:
                    for task in active_tasks: task.cancel()
                    for id, state in self.states.items():
                        if state == "pending": self.states[id] = "cancelled"
                else:
                    for w in self.plan.work:
                        if self.states[w.id] != "pending": continue
                        reason, _ = self.reason(w)
                        if reason in ("upstream failure", "ordering predecessor failed"):
                            self.states[w.id] = "blocked"
                            self.event("blocked", w.node, w.id)
                        elif reason == "ready":
                            self.states[w.id] = "running"
                            self.active[self.nodes[w.node].resource] += 1
                            if self.paused: self.steps -= 1
                            self.event("dispatched", w.node, w.id)
                            task = asyncio.create_task(self.invoke(w))
                            active_tasks.add(task)
                            task.add_done_callback(active_tasks.discard)
                self.owner.sweep(self.states, self.wakeup)
                if not any(s in ("pending", "running") for s in self.states.values()):
                    failed_science = any(self.states[w.id] in ("failed", "blocked") and self.nodes[w.node].branch == "science" for w in self.plan.work)
                    failed_any = any(s in ("failed", "blocked") for s in self.states.values())
                    outcome = "cancelled" if self.cancelled else "failed" if failed_science else "partial" if failed_any else "complete"
                    break
            await self.wakeup.wait()
        if active_tasks:
            await asyncio.gather(*active_tasks, return_exceptions=True)
        return outcome

    def snapshot(self):
        with self.lock:
            nodes = []
            for n, camera in [(n, cam) for n in self.plan.nodes for cam in
                              ([None, *range(self.plan.config['cameras'])] if n.scope == 'camera_frame' else [None])]:
                works = [w for w in self.plan.work if w.node == n.id and (camera is None or w.camera == camera)]
                counts = Counter(self.states[w.id] for w in works)
                reasons = Counter()
                blocked = []
                for w in works:
                    if self.states[w.id] == "pending":
                        reason, missing = self.reason(w)
                        reasons[reason] += 1
                        if len(blocked) < 4:
                            blocked.append(dict(work=w.id, reason=reason, waiting_on=missing))
                state = "running" if counts["running"] else "failed" if counts["failed"] else "blocked" if counts["blocked"] else "complete" if counts["complete"] == len(works) else "cancelled" if counts["cancelled"] else "held" if n.id in self.held else "pending"
                artifacts = [self.artifacts[w.id] for w in works if w.id in self.artifacts]
                latest = next(iter(artifacts[-1].values())) if artifacts else None
                nodes.append(dict(id=n.id if camera is None else f'{n.id}@{camera}', logical_id=n.id, camera=camera,
                                  state=state, counts=dict(counts), total=len(works), reasons=dict(reasons),
                                  examples=blocked, held=n.id in self.held, fail_armed=n.id in self.fail_next,
                                  timing=dict(self.timing[n.id]), sample=asdict(latest) if latest else None))
            edges = []
            for n in self.plan.nodes:
                for b in n.inputs:
                    waiting, available = 0, 0
                    for w in self.plan.work:
                        if w.node != n.id or self.states[w.id] != "pending": continue
                        ids = dict(w.inputs)[b.port]
                        available += sum(d in self.artifacts for d in ids)
                        waiting += sum(d not in self.artifacts for d in ids)
                    edges.append(dict(id=f"{n.id}:{b.port}", available_references=available, missing_references=waiting))
            return dict(id=self.id, revision=self.revision, graph_digest=self.plan.digest, status=self.status,
                        paused=self.paused, elapsed_s=round((self.finished or monotonic())-self.started, 3),
                        nodes=[n for n in nodes if n['camera'] is None],
                        partition_nodes=[n for n in nodes if n['camera'] is not None],
                        edges=edges, resources=dict(self.active), events=list(self.events),
                        resource_lifetimes=self.owner.describe(),
                        artifacts=len(self.artifacts), retained_bytes=self.retained_bytes, memory_budget=self.max_bytes,
                        science_complete=(all(self.states[w.id] == "complete" for w in self.plan.work if self.nodes[w.node].branch == "science")
                            and all(r['state'] == 'closed' for key, r in self.owner.records.items() if 'science' in self.owner.branches[key])))
