"""Process reference recordings through the standard FreeMoCap pipelines."""

import argparse
import json
import logging
from pathlib import Path

from . import workflow
from .catalog import acquire_recording
from .inspection import inspect_recording


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--recordings-root', type=Path, default=Path.home() / 'freemocap_data/recordings')
    common.add_argument('--prepared-root', type=Path, default=Path.home() / 'freemocap_data/testing/prepared')
    actions = command.add_subparsers(dest='action', required=True)
    for action in ('status', 'acquire', 'calibrate', 'process', 'process-all', 'validate', 'recover'):
        sub = actions.add_parser(action, parents=[common])
        if action != 'process-all':
            sub.add_argument('dataset', choices=tuple(workflow.DATASETS))
        if action in ('process', 'process-all', 'calibrate'):
            sub.add_argument('--timeout', type=float, default=1800.0, help='Seconds per pipeline')
            sub.add_argument('--dry-run', action='store_true', help='Show work and paths without changing files')
        if action in ('process', 'process-all'):
            sub.add_argument('--calibration', help='fresh, existing, or a TOML path; full runs default to fresh')
            sub.add_argument('--alignment', choices=('auto', 'calibration', 'person'), help='Default: auto')
            sub.add_argument('--from', dest='start', choices=workflow.STARTS, default='observations')
            sub.add_argument('--run-id', type=int)
            sub.add_argument('--sensor-group')
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    names = tuple(workflow.DATASETS) if args.action == 'process-all' else (args.dataset,)
    try:
        for name in names:
            roots = dict(recordings_root=args.recordings_root, prepared_root=args.prepared_root)
            if args.action == 'status':
                result = workflow.status(name, **roots)
            elif args.action == 'acquire':
                acquire_recording(workflow.DATASETS[name], recordings_root=args.recordings_root)
                result = inspect_recording(workflow.DATASETS[name], recordings_root=args.recordings_root)
            elif args.action == 'validate':
                result = workflow.validate(name, prepared_root=args.prepared_root)
            elif args.action == 'recover':
                result = workflow.recover_dataset(name, prepared_root=args.prepared_root)
            else:
                options = dict(roots, operation='calibrate' if args.action == 'calibrate' else 'process',
                               timeout=args.timeout)
                if args.action != 'calibrate':
                    options.update(start=args.start, calibration=args.calibration, alignment=args.alignment,
                                   run_id=args.run_id, sensor_group=args.sensor_group)
                result = workflow.preflight(name, **options) if args.dry_run else str(workflow.process(name, **options))
            print(json.dumps(result, indent=2), flush=True)
    except (ValueError, OSError, RuntimeError, KeyError) as error:
        logging.error('%s: %s', name, error)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
