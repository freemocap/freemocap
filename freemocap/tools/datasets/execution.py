"""Dataset execution identity and measured worker outcomes, independent of readiness."""

from contextlib import contextmanager
from pathlib import Path
import subprocess
from time import perf_counter

from .storage import write_json


def require_implementation(value: str) -> str:
    """Reject unavailable paths before acquisition, output mutation or model setup."""
    if value == 'graph':
        raise ValueError('Graph posthoc execution is not implemented; no processing was started')
    if value != 'current':
        raise ValueError(f'Unknown posthoc implementation: {value}')
    return value


@contextmanager
def measure_worker(*, report_path: Path, implementation: str, operation: str):
    """Persist failures too; worker success does not certify output acceptance.

    Includes subprocess launch, model setup, processing, worker validation, log
    draining and shutdown. It deliberately does not claim inference-only timing.
    """
    require_implementation(implementation)
    started = perf_counter()
    report = dict(version=1, implementation=implementation, operation=operation,
                  scope='worker_lifecycle', status='running', elapsed_s=None,
                  error=None)
    write_json(report_path, report)
    try:
        yield report
    except BaseException as error:
        report['status'] = ('timeout' if isinstance(error, subprocess.TimeoutExpired)
                            else 'interrupted' if isinstance(error, KeyboardInterrupt)
                            else 'failed')
        report['error'] = dict(type=type(error).__name__, message=str(error))
        raise
    else:
        report['status'] = 'complete'
    finally:
        report['elapsed_s'] = perf_counter() - started
        write_json(report_path, report)
