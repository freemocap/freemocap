"""Execute recording-level typed bindings, independently of observation clients.

Frame loading/tracking retain their bounded streaming adapter internally. This
executor does not pretend a recording artifact is an individual frame token.
"""
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED, CancelledError
from dataclasses import dataclass, field
from time import perf_counter
import traceback

from freemocap.core.pipeline.dataflow.definition import CompiledGraph, InputBindingRule, DataGranularity


@dataclass
class RecordingExecutionResult:
    outputs: dict[str, dict[str, object]] = field(default_factory=dict)
    failures: dict[str, str] = field(default_factory=dict)
    failure_tracebacks: dict[str, str] = field(default_factory=dict)
    blocked: dict[str, tuple[str, ...]] = field(default_factory=dict)
    elapsed_seconds: dict[str, float] = field(default_factory=dict)
    started_seconds: dict[str, float] = field(default_factory=dict)
    finished_seconds: dict[str, float] = field(default_factory=dict)
    cancelled: bool = False

    @property
    def complete(self) -> bool:
        return not self.failures and not self.blocked and not self.cancelled


def execute_recording_graph(*, graph: CompiledGraph,
    handlers: Mapping[str, Callable[[dict[str, object]], dict[str, object]]],
    resource_capacity: Mapping[str, int] | None = None,
    cancelled: Callable[[], bool] = lambda: False,
) -> RecordingExecutionResult:
    """Dispatch ready operations; isolate failures and reserve annotation capacity.

    Return after all admitted work drains. Handlers own cooperative cancellation
    within native calls. No network consumer or progress callback is on this path.
    """
    capacities = dict(resource_capacity or {"compute": 2, "annotation": 2, "recording_io": 1})
    nodes = {node.id: node for node in graph.definition.nodes}
    if any(node.operation not in handlers or node.execution_resource not in capacities for node in nodes.values()):
        raise ValueError("Every operation requires a registered handler and execution resource")
    if any(value < 1 for value in capacities.values()):
        raise ValueError("Execution capacity must be positive")
    if any(port.contract.data_granularity != DataGranularity.RECORDING
           for node in nodes.values() for port in (*node.inputs, *node.outputs)) or any(
           edge.binding != InputBindingRule.SAME_KEY for edge in graph.definition.edges):
        raise ValueError("Recording executor requires recording-level same-key bindings")
    incoming = {node: [edge for edge in graph.definition.edges if edge.target.node == node] for node in nodes}
    result = RecordingExecutionResult()
    execution_started = perf_counter()
    pending = set(nodes)
    running = {}
    pools = {name: ThreadPoolExecutor(max_workers=count, thread_name_prefix=f"graph-{name}")
             for name, count in capacities.items()}

    def invoke(node_id: str, inputs: dict[str, object]):
        start = perf_counter()
        result.started_seconds[node_id] = start - execution_started
        try:
            if cancelled():
                raise CancelledError("Recording execution cancelled")
            output = handlers[nodes[node_id].operation](inputs)
            if set(output) != {port.name for port in nodes[node_id].outputs}:
                raise ValueError(f"Operation {node_id} returned undeclared/missing output ports")
            return output
        finally:
            result.elapsed_seconds[node_id] = perf_counter() - start
            result.finished_seconds[node_id] = perf_counter() - execution_started

    try:
        while pending or running:
            result.cancelled = result.cancelled or cancelled()
            for node_id in graph.topological_order:
                if node_id not in pending:
                    continue
                parents = {edge.source.node for edge in incoming[node_id]}
                failed = parents.intersection(result.failures.keys() | result.blocked.keys())
                if failed or result.cancelled:
                    result.blocked[node_id] = tuple(sorted(failed))
                    pending.remove(node_id)
                elif parents.issubset(result.outputs):
                    resource = nodes[node_id].execution_resource
                    if sum(nodes[value].execution_resource == resource for value in running.values()) >= capacities[resource]:
                        continue
                    inputs = {edge.target.port: result.outputs[edge.source.node][edge.source.port] for edge in incoming[node_id]}
                    running[pools[resource].submit(invoke, node_id, inputs)] = node_id
                    pending.remove(node_id)
            if running:
                finished, _ = wait(running, return_when=FIRST_COMPLETED, timeout=0.1)
                for future in finished:
                    node_id = running.pop(future)
                    try:
                        result.outputs[node_id] = future.result()
                    except Exception as error:
                        result.failures[node_id] = f"{type(error).__name__}: {error}"
                        result.failure_tracebacks[node_id] = traceback.format_exc()
            elif pending:
                raise RuntimeError("Compiled graph has unresolved prerequisites")
    finally:
        for pool in pools.values():
            pool.shutdown(wait=True, cancel_futures=True)
    return result
