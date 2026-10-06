"""Execution process: no HTTP, WebSocket, controller locks or browser state."""
from concurrent.futures import CancelledError
from dataclasses import asdict
from contextlib import redirect_stdout, redirect_stderr
import json
import os
from pathlib import Path
from queue import Full
import traceback

from experiments.executable_graph_lab.graph.runtime import Executor


class ReportPublisher:
    """Best-effort bounded IPC. A full transport drops reports, never waits."""
    def __init__(self, queue):
        self.queue = queue
        self.dropped = 0

    def __call__(self, snapshot):
        try:
            self.queue.put_nowait(dict(snapshot=snapshot, worker_pid=os.getpid(), dropped_reports=self.dropped))
        except Full:
            self.dropped += 1


def execute(plan, handlers, capacities, output, reports, cancelled, paused, setup=None, metadata=None):
    """Reusable child-process entry for real adapters and isolation tests."""
    publisher = ReportPublisher(reports)
    executor = Executor(plan, handlers, capacities, cancelled=cancelled, observer=publisher)
    executor.paused = paused
    if setup: setup(executor)
    error = None
    try:
        executor.run()
    except BaseException as exc:
        error = str(exc)
        if not isinstance(exc,CancelledError): traceback.print_exc()
    # Final state is durable independently of report delivery or server availability.
    summary = executor.snapshot() | dict(error=error, worker_pid=os.getpid(),
        dropped_reports=publisher.dropped, results={k:asdict(v) if hasattr(v,'__dataclass_fields__') else v for k,v in executor.results.items()})
    if metadata: summary.update(metadata())
    output.mkdir(parents=True, exist_ok=True)
    (output/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in executor.events),encoding='utf-8')
    (output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    publisher(summary)
    # Never wait for the queue's feeder to flush to a missing/slow server.
    reports.cancel_join_thread()
    return summary


def run_tracking(context, config, destination, output, reports, cancelled, paused):
    from experiments.executable_graph_lab.graph.tracking import tracking_plan, TrackingAdapters
    # Native model creation and all file/data processing belong to this process.
    with (output/'worker.log').open('a',encoding='utf-8',buffering=1) as log, redirect_stdout(log), redirect_stderr(log):
        try:
            plan = tracking_plan(context,destination)
            adapters = TrackingAdapters(context,config,destination)
            execute(plan,adapters.handlers(),dict(cpu=1,io=len(context.videos),gpu=1),output,reports,cancelled,paused,
                    setup=lambda executor:setattr(adapters,'executor',executor),
                    metadata=lambda:dict(source=str(context.source),output_directory=str(output),providers=adapters.provider_report))
        except BaseException:
            traceback.print_exc()
            raise
