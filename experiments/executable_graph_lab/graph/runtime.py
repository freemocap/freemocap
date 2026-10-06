"""Typed keyed DAG execution. Bindings govern both dispatch and graph export.

Thread workers own synchronous library calls. Cancellation stops admission and
drains running calls before closing resources; it never pretends a GPU call was
interrupted. Pixel artifacts are released after their last declared consumer.
"""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED, CancelledError
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from threading import Event
from multiprocessing.synchronize import Event as ProcessEvent
from time import perf_counter
from typing import Callable


@dataclass(frozen=True)
class Binding:
    port: str
    source: str
    payload: type
    rule: str  # broadcast, same_key, all_sources, sealed


@dataclass(frozen=True)
class Window:
    consumer: str
    frames: int


@dataclass(frozen=True)
class Node:
    id: str
    label: str
    scope: str
    resource: str
    payload: type
    inputs: tuple[Binding, ...] = ()
    ordered: bool = False
    io_role: str = 'none'
    io_files: tuple[str, ...] = ()
    window: Window | None = None
    lifetime_users: tuple[str, ...] = ()
    description: str = ''
    work_unit: str = 'operations'


@dataclass(frozen=True)
class Work:
    id: str
    node: str
    frame: int | None
    camera: str | None
    inputs: tuple[tuple[str, tuple[str, ...]], ...]
    predecessor: str | None


@dataclass(frozen=True)
class Plan:
    nodes: tuple[Node, ...]
    work: tuple[Work, ...]
    cameras: tuple[str, ...]
    frames: int

    def describe(self):
        nodes = []
        for n in self.nodes:
            inputs = [dict(port=b.port, source=b.source, source_slot='out', data_type=b.payload.__name__, rule=b.rule) for b in n.inputs]
            nodes.append(dict(id=n.id, label=n.label, scope=n.scope, resource=n.resource,
                description=n.description, work_unit=n.work_unit, ordered=n.ordered, io_role=n.io_role, io_files=[dict(path=p, contents=n.label) for p in n.io_files],
                outputs=[dict(name='out', data_type=n.payload.__name__)], inputs=inputs,
                input_slots=[dict(name=b.port, data_type=b.payload.__name__, required=True) for b in n.inputs],
                admission_window=dict(consumer=n.window.consumer, frames=n.window.frames) if n.window else None,
                lifetime_users=n.lifetime_users))
        edges = [dict(source=b.source, target=n.id, source_slot='out', target_slot=b.port,
                      data_type=b.payload.__name__, rule=b.rule) for n in self.nodes for b in n.inputs]
        value = dict(schema_version=1, synthetic=False, cameras=self.cameras, frames=self.frames,
                     nodes=nodes, edges=edges, work_items=len(self.work), work=[asdict(w) for w in self.work])
        return value | dict(digest=sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:16])


def compile_plan(nodes: tuple[Node, ...], cameras: tuple[str, ...], frames: int) -> Plan:
    if frames < 1 or not cameras or len(set(cameras)) != len(cameras):
        raise ValueError('Expected positive frame count and unique camera identities')
    by_id = {n.id: n for n in nodes}
    if len(by_id) != len(nodes): raise ValueError('Duplicate node')
    ordered, visited = [], set()
    def visit(n, stack):
        if n.id in stack: raise ValueError('Dependency cycle')
        if n.id in visited: return
        if n.scope not in ('recording', 'frame', 'camera_frame'): raise ValueError('Invalid scope')
        if len({b.port for b in n.inputs}) != len(n.inputs): raise ValueError('Duplicate input slot')
        if any(user not in by_id for user in n.lifetime_users): raise ValueError('Unknown resource lifetime user')
        if n.window and (n.window.consumer not in by_id or n.window.frames < 1 or n.scope!='camera_frame'
                         or by_id[n.window.consumer].scope!='frame'): raise ValueError('Invalid admission window')
        for b in n.inputs:
            if b.source not in by_id or by_id[b.source].payload is not b.payload:
                raise ValueError('Unknown producer or incompatible payload')
            visit(by_id[b.source], stack | {n.id})
        visited.add(n.id)
        ordered.append(n)
    for node in nodes: visit(node, set())
    keys, work = {}, []
    def identity(node, frame, camera): return f'{node}/{frame}/{camera}'
    for n in ordered:
        keys[n.id] = [(None, None)] if n.scope=='recording' else [
            (f, c) for f in range(frames) for c in (cameras if n.scope=='camera_frame' else [None])]
        for f, c in keys[n.id]:
            inputs = []
            for b in n.inputs:
                scope = by_id[b.source].scope
                if b.rule=='broadcast' and scope=='recording': selected = [(None, None)]
                elif b.rule=='same_key' and scope==n.scope: selected = [(f, c)]
                elif b.rule=='all_sources' and scope=='camera_frame' and n.scope=='frame': selected = [(f, camera) for camera in cameras]
                elif b.rule=='sealed' and n.scope=='recording': selected = keys[b.source]
                else: raise ValueError('Incompatible binding key rule')
                inputs.append((b.port, tuple(identity(b.source, *key) for key in selected)))
            previous = identity(n.id, f-1, c) if n.ordered and f is not None and f>0 else None
            work.append(Work(identity(n.id, f, c), n.id, f, c, tuple(inputs), previous))
    return Plan(tuple(ordered), tuple(work), cameras, frames)


class Executor:
    def __init__(self, plan: Plan, handlers: dict[str, Callable], capacities: dict[str, int],
                 cancelled: Event | ProcessEvent | None = None, observer: Callable | None = None):
        self.plan, self.handlers = plan, handlers
        if set(handlers) != {n.id for n in plan.nodes}: raise ValueError('Handlers must match graph nodes')
        if any(capacities.get(n.resource, 0)<1 for n in plan.nodes): raise ValueError('Missing resource capacity')
        self.capacities, self.cancelled, self.observer = capacities, cancelled or Event(), observer
        self.nodes = {n.id: n for n in plan.nodes}
        self.graph_digest = plan.describe()['digest']
        self.states = {w.id: 'pending' for w in plan.work}
        self.artifacts, self.results, self.events = {}, {}, []
        self.references = Counter(d for w in plan.work for _, deps in w.inputs for d in deps)
        self.stats = {n.id: dict(calls=0, seconds=0., max_seconds=0., first_started_s=None, last_finished_s=None) for n in plan.nodes}
        self.peak_pixel_bytes = 0
        self.status = 'created'
        self.paused = Event()
        self.started = perf_counter()
        self.finished_at = None
        self.last_observed = 0.
        self.observer_seconds = 0.
        self.pools = {}
        self.finalizers = []
        self.cleanup_tasks = {}
        self.lifetimes = {}

    def own(self, resource: str, close: Callable, owner: Work | None = None):
        """Register immediately after acquisition, before any fallible initialization."""
        self.finalizers.append((resource, close, owner))

    @staticmethod
    def close_group(closers):
        error = None
        for close in reversed(closers):
            try: close()
            except BaseException as exc:
                if error is None: error = exc
        if error: raise error

    def release_ready(self):
        groups = {}
        for resource, close, owner in self.finalizers:
            if owner is None: continue
            node = self.nodes[owner.node]
            key = (owner.node, owner.camera)
            if not node.lifetime_users or key in self.lifetimes: continue
            users = [w for w in self.plan.work if w.node in node.lifetime_users and (owner.camera is None or w.camera==owner.camera)]
            if all(self.states[w.id]=='complete' for w in users):
                groups.setdefault(key,(resource,[]))[1].append(close)
        for key,(resource,closers) in groups.items():
            self.lifetimes[key] = 'closing'
            future = self.pools[resource].submit(self.close_group,closers)
            self.cleanup_tasks[future] = key

    def snapshot(self):
        return dict(status=self.status, paused=self.paused.is_set(), graph_digest=self.graph_digest, elapsed_s=0. if self.status=='created' else (self.finished_at or perf_counter())-self.started, observer_seconds=self.observer_seconds, states=dict(self.states),
                    timings={k: dict(v) for k,v in self.stats.items()}, peak_pixel_bytes=self.peak_pixel_bytes,
                    resource_lifetimes=[dict(node=n,camera=c,state=s) for (n,c),s in self.lifetimes.items()],
                    events=list(self.events[-100:]))

    def emit(self, kind, work='', detail=''):
        self.events.append(dict(kind=kind, work=work, detail=detail, at=perf_counter()-self.started))
        now = perf_counter()
        if self.observer and (now-self.last_observed >= .25 or kind in ('complete','failed','cancelled','cleanup_failed')):
            self.last_observed = now
            self.observer(self.snapshot())
            self.observer_seconds += perf_counter()-now

    def invoke(self, work, inputs):
        started = perf_counter()
        value = self.handlers[work.node](work, inputs)
        if not isinstance(value, self.nodes[work.node].payload):
            raise TypeError(f'{work.id}: handler returned wrong payload type')
        return value, started-self.started, perf_counter()-started

    def run(self):
        self.started = perf_counter()
        self.pools = {r: ThreadPoolExecutor(max_workers=c, thread_name_prefix=f'graph-{r}') for r,c in self.capacities.items()}
        active, usage, error = {}, Counter(), None
        self.status = 'running'
        try:
            while any(s in ('pending','running') for s in self.states.values()) or self.cleanup_tasks:
                if self.cancelled.is_set(): raise CancelledError('Graph cancelled; draining admitted work')
                for future,key in list(self.cleanup_tasks.items()):
                    if future.done():
                        del self.cleanup_tasks[future]
                        try: future.result()
                        except BaseException:
                            self.lifetimes[key] = 'cleanup_failed'
                            raise
                        self.lifetimes[key] = 'closed'
                        self.emit('resource_closed',detail=str(key))
                self.release_ready()
                if all(s=='complete' for s in self.states.values()) and not self.cleanup_tasks: break
                for w in self.plan.work:
                    if self.paused.is_set(): break
                    if self.states[w.id] != 'pending': continue
                    n = self.nodes[w.node]
                    deps = [d for _, ids in w.inputs for d in ids]
                    if any(self.states[d]!='complete' for d in deps): continue
                    if w.predecessor and self.states[w.predecessor]!='complete': continue
                    if usage[n.resource] >= self.capacities[n.resource]: continue
                    if n.window:
                        unfinished = [v.frame for v in self.plan.work if v.node==n.window.consumer and self.states[v.id]!='complete']
                        if unfinished and w.frame >= min(unfinished) + n.window.frames: continue
                    inputs = {port: tuple(self.artifacts[d] for d in ids) for port, ids in w.inputs}
                    self.states[w.id] = 'running'
                    usage[n.resource] += 1
                    active[self.pools[n.resource].submit(self.invoke, w, inputs)] = w
                    self.emit('dispatched', w.id)
                if not active:
                    if self.paused.is_set():
                        self.cancelled.wait(.05)
                        self.emit('paused_wait')
                        continue
                    if self.cleanup_tasks:
                        wait(self.cleanup_tasks,timeout=.05,return_when=FIRST_COMPLETED)
                        continue
                    raise RuntimeError('Graph cannot make progress')
                finished, _ = wait(active, timeout=.05, return_when=FIRST_COMPLETED)
                for future in finished:
                    w = active.pop(future)
                    usage[self.nodes[w.node].resource] -= 1
                    try: value, started, seconds = future.result()
                    except BaseException:
                        self.states[w.id] = 'failed'
                        raise
                    self.states[w.id] = 'complete'
                    stats = self.stats[w.node]
                    stats['calls'] += 1
                    stats['seconds'] += seconds
                    stats['max_seconds'] = max(stats['max_seconds'], seconds)
                    stats['first_started_s'] = started if stats['first_started_s'] is None else min(stats['first_started_s'],started)
                    stats['last_finished_s'] = max(stats['last_finished_s'] or 0.,started+seconds)
                    if self.references[w.id]: self.artifacts[w.id] = value
                    else: self.results[w.node] = value
                    self.peak_pixel_bytes = max(self.peak_pixel_bytes, sum(getattr(a, 'pixel_bytes', 0) for a in self.artifacts.values()))
                    for _, ids in w.inputs:
                        for d in ids:
                            self.references[d] -= 1
                            if self.references[d]==0: self.artifacts.pop(d, None)
                    self.emit('completed', w.id)
        except BaseException as exc:
            error = exc
        finally:
            # Native inference is not interruptible; drain before closing its session.
            for future in active:
                try: future.result()
                except BaseException as exc:
                    if error is None: error = exc
            for future,key in list(self.cleanup_tasks.items()):
                try:
                    future.result()
                    self.lifetimes[key] = 'closed'
                except BaseException as exc:
                    self.lifetimes[key] = 'cleanup_failed'
                    if error is None: error = exc
            remaining = {}
            for index,(resource,close,owner) in enumerate(self.finalizers):
                key = (owner.node,owner.camera) if owner else (f'unscoped-{index}',None)
                if key in self.lifetimes: continue
                remaining.setdefault(key,(resource,[]))[1].append(close)
            for key,(resource,closers) in reversed(list(remaining.items())):
                try:
                    self.pools[resource].submit(self.close_group,closers).result()
                    self.lifetimes[key] = 'closed'
                    self.emit('resource_closed', detail=str(key))
                except BaseException as exc:
                    self.lifetimes[key] = 'cleanup_failed'
                    self.emit('cleanup_failed', detail=str(exc))
                    if error is None: error = exc
            for pool in self.pools.values(): pool.shutdown(wait=True)
            self.artifacts.clear()
            if error:
                for key, state in self.states.items():
                    if state in ('pending','running'): self.states[key] = 'cancelled' if isinstance(error, CancelledError) else 'blocked'
            self.status = 'cancelled' if isinstance(error, CancelledError) else 'failed' if error else 'complete'
            self.finished_at = perf_counter()
            self.emit(self.status, detail=str(error) if error else '')
        if error: raise error
        return self.results
