"""Plain-text reports of recorded measurements; no processing or acceptance side effects."""
import json
from pathlib import Path
import re
import sys


def cell(value) -> str:
    if value is None:
        return 'not recorded'
    if isinstance(value, float):
        return f'{value:.6g}'
    return str(value).replace('\n', ' / ')


def table(columns, rows) -> str:
    rows = [[cell(value) for value in row] for row in rows]
    widths = [max([len(str(column)), *(len(row[i]) for row in rows)])
              for i, column in enumerate(columns)]
    def line(row):
        return '  '.join(str(value).ljust(width) for value, width in zip(row, widths))
    return '\n'.join([line(columns), line(['-' * width for width in widths]),
                      *(line(row) for row in rows)])


def leaves(value, prefix=''):
    if isinstance(value, dict):
        for name, item in value.items():
            yield from leaves(item, f'{prefix}.{name}' if prefix else name)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from leaves(item, f'{prefix}[{index}]')
    else:
        yield prefix, value


def render_report(result: dict, *, log_path: Path, label: str, identity=None) -> str:
    lines = ['FREEMOCAP DATASET REPORT', '=' * 78, label,
             f'Processing log: {log_path}',
             'Recorded evidence only. Rendering this report does not revalidate saved files.', '']
    lines += ['EXECUTION', table(['Field', 'Recorded value'], [
        ['Implementation', result.get('implementation')],
        *list(leaves(result.get('performance', {}), 'performance')),
        *[(f'{name}.{field}', result[name].get(field))
          for name in ('calibration_task', 'mocap_task') if result.get(name)
          for field in ('status', 'created_at', 'updated_at')]])]
    lines += ['', 'WORKLOAD / SOFTWARE IDENTITY',
              table(['Field', 'Recorded value'], list(leaves(identity or {})) or [['Identity', None]])]
    lines += ['', 'EXECUTED SETTINGS',
              table(['Setting', 'Value'], list(leaves(result.get('mocap_config', {}))) or [['Settings', None]])]
    timing_rows, statistics, summaries = [], [], []
    malformed = 0
    if log_path.is_file():
        with log_path.open(encoding='utf-8', errors='replace') as source:
            for raw in source:
                line = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', raw).replace('\x00', '').strip()
                if 'Processing statistics: ' in line:
                    try:
                        record = json.loads(line.split('Processing statistics: ', 1)[1])
                        if 'columns' in record:
                            rendered = table(record['columns'], record['rows'])
                        else:
                            rendered = table(['Metric', 'Value'], list(record['values'].items()))
                        statistics.extend(['', record['stage'], rendered, record.get('caption', '')])
                    except (ValueError, KeyError, TypeError, IndexError):
                        malformed += 1
                if re.match(r'^\S+ \| \d+ \| [-+\d.eE]+ \|', line):
                    row = line.split(' | ')
                    if len(row) == 7:
                        timing_rows.append(row)
                if any(line.startswith(prefix) for prefix in (
                    'Posthoc performance [', 'Detection throughput:', 'Completed detection:',
                    'Detector=', 'Recording:', 'Settings:', 'Iterations:', 'Native solve (ms):', 'Converged:')):
                    summaries.append(line)
    else:
        summaries.append('Processing log unavailable; no timing inferred.')
    lines += ['', 'PROCESSING TIMING', *summaries,
              'Wall-clock spans overlap: do not add rows. These are not GPU kernel times.',
              table(['Operation', 'Calls', 'Total s', 'Mean ms', 'First ms', 'Mean after first ms', 'Max ms'], timing_rows)
              if timing_rows else 'Detailed operation timing: not recorded.',
              '', 'NUMERICAL DIAGNOSTICS', *(statistics or ['No structured numerical log records.'])]
    if malformed:
        lines.append(f'Unrecognized diagnostic records: {malformed}; inspect original log.')
    lines += ['', 'SAVED VALIDATION RESULTS',
              table(['Check', 'Recorded value'], list(leaves(result.get('validation') or {})) or [['Validation', None]]),
              '', 'CALIBRATION RESULTS',
              table(['Field', 'Recorded value'], list(leaves(result.get('calibration') or {})) or [['Calibration', None]]),
              '', 'INTERPRETATION',
              'Missing measurements remain unavailable, never zero. No speedup is inferred.',
              'Task timestamps are lifecycle metadata, not precise operation timings.',
              'Distribution percentiles describe samples, not uncertainty across repeated runs.',
              'Older results may predate current output acceptance requirements.', '']
    return '\n'.join(lines)


def report_saved(marker_path: Path) -> str:
    marker = json.loads(marker_path.read_text(encoding='utf-8'))
    log = Path(marker.get('log') or marker_path.parent / 'current' / 'processing.log')
    if not log.is_file():
        log = marker_path.parent / 'current' / 'processing.log'
    return render_report(marker['result'], log_path=log,
                         label=f'Saved reference: {marker_path}', identity=marker.get('identity'))


if __name__ == '__main__':
    print(report_saved(Path(sys.argv[1])))
