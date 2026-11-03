"""Plain-text reports of recorded measurements; no processing or acceptance side effects."""
import json
import math
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


def parse_performance(lines) -> list[dict]:
    """Prefer full-precision events; recover both historical display-table formats."""
    reports = {}
    current = None
    for raw in lines:
        line = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', raw).replace('\x00', '').strip()
        if 'Processing performance: ' in line:
            try:
                report = json.loads(line.split('Processing performance: ', 1)[1])
                if report['version'] == 1 and isinstance(report['stages'], dict):
                    report['source'] = 'structured'
                    reports[report['pipeline_id']] = report
            except (ValueError, KeyError, TypeError):
                pass  # Historical table remains usable when a structured line is truncated.
            continue
        header = re.match(r'^(Posthoc|Dataset worker) performance \[(.+)\] outcome=(\S+); wall=([\d.eE+-]+)s', line)
        if header:
            current = dict(version=1, pipeline_id=header[2], scope='posthoc' if header[1] == 'Posthoc' else 'dataset_worker',
                           outcome=header[3], elapsed_s=float(header[4]), frames=None, images=None,
                           stages={}, counts={}, source='log_table_rounded')
            reports.setdefault(header[2], current)
            continue
        frames = re.match(r'^Completed detection: (\d+) synchronized frames; (\d+) camera images.', line)
        if frames and current is not None:
            current.update(frames=int(frames[1]), images=int(frames[2]))
        counter = re.match(r'^count (\S+): (\d+)$', line)
        if counter and current is not None:
            current['counts'][counter[1]] = int(counter[2])
        cells = [part.strip() for part in line.strip('|').split('|')]
        if len(cells) != 7 or not cells[1].isdigit():
            continue
        try:
            count = int(cells[1])
            values = [None if value == '-' else float(value) for value in cells[2:]]
            if count < 1 or any(value is not None and not math.isfinite(value) for value in values):
                continue
        except ValueError:
            continue
        if current is None:
            current = dict(version=1, pipeline_id='legacy', scope='posthoc', outcome=None,
                           elapsed_s=None, frames=None, images=None, stages={}, counts={}, source='log_table_rounded')
            reports['legacy'] = current
        current['stages'][cells[0]] = dict(count=count, total_s=values[0], mean_ms=values[1],
                                          first_ms=values[2], mean_after_first_ms=values[3] if count > 1 else None,
                                          max_ms=values[4])
    return list(reports.values())


def read_performance(log_path: Path) -> list[dict]:
    if not log_path.is_file():
        return []
    with log_path.open(encoding='utf-8', errors='replace') as source:
        return parse_performance(source)


def normalized_stages(report):
    for name, stage in report['stages'].items():
        yield name, dict(stage,
            amortized_ms_per_frame=1000 * stage['total_s'] / report['frames'] if report.get('frames') else None,
            amortized_ms_per_image=1000 * stage['total_s'] / report['images'] if report.get('images') else None)


def performance_tables(reports) -> str:
    sections = []
    for report in reports:
        sections += [f"{report['scope']} / {report['pipeline_id']} / {report.get('outcome')} / source={report['source']}",
                     f"Wall: {cell(report.get('elapsed_s'))} s; synchronized frames: {cell(report.get('frames'))}; camera images: {cell(report.get('images'))}",
                     table(['Operation', 'Calls', 'Total s', 'Mean ms/call', 'First ms', 'After first ms', 'Max ms', 'Amortized ms/frame', 'Amortized ms/image'],
                           [[name, stage['count'], stage['total_s'], stage['mean_ms'], stage['first_ms'], stage['mean_after_first_ms'], stage['max_ms'],
                             stage['amortized_ms_per_frame'], stage['amortized_ms_per_image']] for name, stage in normalized_stages(report)])]
    return '\n\n'.join(sections) if sections else 'Detailed operation timing: not recorded.'


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
    statistics, summaries, log_lines = [], [], []
    malformed = 0
    if log_path.is_file():
        with log_path.open(encoding='utf-8', errors='replace') as source:
            for raw in source:
                log_lines.append(raw)
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
                if any(line.startswith(prefix) for prefix in (
                    'Posthoc performance [', 'Detection throughput:', 'Completed detection:',
                    'Detector=', 'Recording:', 'Settings:', 'Iterations:', 'Native solve (ms):', 'Converged:')):
                    summaries.append(line)
    else:
        summaries.append('Processing log unavailable; no timing inferred.')
    lines += ['', 'PROCESSING TIMING', *summaries,
              'Wall-clock spans overlap: do not add rows. These are not GPU kernel times.',
              performance_tables(result.get('timing_reports') or parse_performance(log_lines)),
              'Amortized per-frame/image costs divide total work by the recording size; they are not individual-frame latency percentiles.',
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
