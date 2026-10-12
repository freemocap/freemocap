"""Diagnostic-only serial replay of real recording handlers, without graph overlap."""
import cProfile
import json
from pathlib import Path
import pstats
from time import perf_counter, process_time
import traceback

from freemocap.core.pipeline.dataflow.recording_executor import RecordingExecutionResult


def measure_isolated_components(*, graph, handlers, output: Path, profile: bool = False) -> RecordingExecutionResult:
    """Preserve typed bindings and failures; isolate handlers, not their native work.

    This is a measurement tool, never an alternative production scheduler.
    CPU time includes native threads in this process, excludes child processes.
    Profiling covers the calling thread only and must not be used as a baseline.
    """
    output.mkdir(parents=True, exist_ok=True)
    result = RecordingExecutionResult()
    nodes = {node.id: node for node in graph.definition.nodes}
    measurements = {}
    origin = perf_counter()
    for node_id in graph.topological_order:
        node = nodes[node_id]
        incoming = [edge for edge in graph.definition.edges if edge.target.node == node_id]
        failed = tuple(sorted({edge.source.node for edge in incoming
                              if edge.source.node not in result.outputs}))
        if failed:
            result.blocked[node_id] = failed
            continue
        inputs = {edge.target.port: result.outputs[edge.source.node][edge.source.port] for edge in incoming}
        profiler = cProfile.Profile() if profile else None
        start = perf_counter()
        cpu = process_time()
        result.started_seconds[node_id] = start - origin
        try:
            if profiler is not None:
                profiler.enable()
            value = handlers[node.operation](inputs)
            if set(value) != {port.name for port in node.outputs}:
                raise ValueError(f"Operation {node_id} returned undeclared/missing output ports")
            result.outputs[node_id] = value
        except Exception as error:
            result.failures[node_id] = str(error)
            result.failure_tracebacks[node_id] = traceback.format_exc()
        finally:
            if profiler is not None:
                profiler.disable()
            elapsed = perf_counter() - start
            result.elapsed_seconds[node_id] = elapsed
            result.finished_seconds[node_id] = perf_counter() - origin
            measurements[node_id] = dict(wall_seconds=elapsed, process_cpu_seconds=process_time()-cpu,
                                         succeeded=node_id in result.outputs)
            if profiler is not None:
                profiler.dump_stats(str(output / f"{node_id}.prof"))
                with (output / f"{node_id}.txt").open('w', encoding='utf-8') as stream:
                    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats('cumtime').print_stats(45)
            (output / 'components.json').write_text(json.dumps(dict(profiled=profile,
                measurements=measurements, blocked=result.blocked), indent=2), encoding='utf-8')
    (output / 'components.json').write_text(json.dumps(dict(profiled=profile,
        measurements=measurements, blocked=result.blocked), indent=2), encoding='utf-8')
    return result
