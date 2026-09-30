"""Small terminal-only view of the worker's existing progress messages."""

import re
import json
import sys
from datetime import datetime

EVENT = re.compile(r'\b(calibration|mocap|validation): (.*?) \((running|complete|failed|cancelled)\)\s*$')
COUNT = re.compile(r'\b(\d+)/(\d+)\b')
COLUMN_GUIDE = {
    'Camera': 'Camera identifier; the filenames are listed below the table.',
    'Metric': 'Measurement name, including its units where applicable.',
    'Value': 'Measured value for the named metric.',
    'Read': 'Video frames decoded and processed.',
    'Expected': 'Total video frames expected from the video metadata.',
    'Fresh': 'Frames processed by a new tracker call.',
    'Cached': 'Frames whose detection results were reused from the observation cache.',
    'Queued': 'Frame results sent to the next processing worker; this does not mean saved to disk.',
    'Wall s': 'Elapsed seconds for this video worker, including decoding and annotation.',
    'Observed': '2D point samples available from this camera across all frames.',
    'Reprojected': 'Observed samples with a reconstructed 3D point and a finite reprojection error.',
    'Contributing': 'Reprojected samples with a positive triangulation weight.',
    'N': 'Number of finite samples used to calculate the statistics.',
    'NaN %': 'Percentage of input samples with a missing or undefined value.',
    'Inf %': 'Percentage of input samples with an infinite value.',
    'Mean': 'Arithmetic average of the finite samples.',
    'SD': 'Population standard deviation of the finite samples.',
    'Min': 'Smallest finite value.',
    'P05': '5th percentile: 5% of finite samples fall at or below this value.',
    'Median': '50th percentile: the middle of the finite sample distribution.',
    'P95': '95th percentile: 95% of finite samples fall at or below this value.',
    'Max': 'Largest finite value, including outliers.',
}


def owner(pipeline: str, detail: str) -> str:
    if pipeline == 'calibration':
        if detail.startswith('Board detection in videos:'):
            return 'SkellyTracker · board corners'
        return 'Calibration'
    if pipeline == 'validation':
        return 'FreeMoCap · validation'
    if 'Detecting and annotating' in detail:
        return 'SkellyTracker · RTMPose'
    if 'Fitting connected' in detail:
        return 'SkellyForge · skeleton fitting'
    return 'FreeMoCap · mocap'


class WorkerProgress:
    """Animate terminals; retain plain progress when redirected or Rich is absent.

    Counts describe the current operation, never an estimated whole-run percentage.
    The worker log is written separately and remains complete.
    """

    def __init__(self, log_path, *, console=None):
        self.log_path = log_path
        self.progress = None
        self.rows = {}
        self.stages = {}
        self.history = {}
        self.video_statistics = []
        self.rate_samples = {}
        self.console = console

    def __enter__(self):
        try:
            from rich.console import Console
            from rich.table import Column
            from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
        except ImportError:
            return self
        self.console = self.console or Console(stderr=True, highlight=False)
        if not self.console.is_terminal or self.console.is_dumb_terminal:
            return self
        self.console.print('FreeMoCap dataset processing', style='bold cyan')
        self.console.print(f'Full log: {self.log_path}', style='dim', markup=False)
        self.console.print('Rates: FR = camera frame in calibration, synchronized frame in tracking. AVG uses the observed count/time interval.', style='dim')
        self.progress = Progress(
            SpinnerColumn(), TextColumn('{task.description}', markup=False,
                                        table_column=Column(max_width=28, no_wrap=True, overflow='ellipsis')),
            BarColumn(bar_width=16, complete_style='cyan', finished_style='green'),
            TextColumn('{task.fields[count]}', markup=False), TimeElapsedColumn(),
            TextColumn('{task.fields[rate]}', style='bold bright_cyan on grey11', markup=False,
                       table_column=Column(no_wrap=True)),
            TextColumn('{task.fields[detail]}', markup=False,
                       table_column=Column(max_width=24, no_wrap=True, overflow='ellipsis')),
            console=self.console, refresh_per_second=4,
        )
        self.progress.start()
        return self

    def rate_text(self, pipeline, stage, detail, completed, total, now):
        """Use count deltas, not the pipeline timer or an assumed zero first count."""
        if total is None:
            self.rate_samples.pop(pipeline, None)
            return ''
        unit = 'FR' if 'frames' in detail else 'item'
        sample = self.rate_samples.get(pipeline)
        if (sample is None or sample['stage'] != stage or sample['total'] != total
                or completed < sample['last'] or now < sample['time']):
            self.rate_samples[pipeline] = dict(stage=stage, total=total, first=completed,
                                               last=completed, time=now)
            return ''
        sample['last'] = completed
        elapsed = now - sample['time']
        if elapsed <= 0:
            return ''
        advanced = completed - sample['first']
        speed = advanced / elapsed
        inverse = f'{elapsed / advanced:.4f}' if advanced else '--'
        sample['average'] = f'AVG  {speed:.2f} {unit}/s  |  {inverse} s/{unit}'
        return f"  | {sample['average']} |  "

    def statistics(self, title, values):
        self.numeric_table(title, ['Metric', 'Value'], list(values.items()))

    def numeric_table(self, title, columns, rows, caption=''):
        guide = '\n'.join(f'{column}: {COLUMN_GUIDE.get(column, "Measured quantity named by this column.")}'
                          for column in columns)
        def cell(value):
            if value is None:
                return 'not available'
            if isinstance(value, float):
                return f'{value:.2e}' if abs(value) >= 10000 else f'{value:.3f}'
            return str(value)

        try:
            from rich import box
            from rich.console import Console, Group
            from rich.table import Table
            from rich.text import Text
        except ImportError:
            lines = [title, guide, ' | '.join(map(str, columns)),
                     *(' | '.join(cell(value) for value in row) for row in rows), caption]
            encoding = sys.stdout.encoding or 'utf-8'
            print('\n'.join(lines).encode(encoding, errors='backslashreplace').decode(encoding), flush=True)
            return

        table = Table(box=box.SIMPLE_HEAVY,
                      padding=(0, 1), header_style='bold', show_edge=False,
                      title_justify='left')
        for index, column in enumerate(columns):
            numeric = all(row[index] is None or isinstance(row[index], (int, float)) for row in rows)
            table.add_column(str(column), justify='right' if numeric else 'left')
        for row in rows:
            table.add_row(*(Text(cell(value)) for value in row))
        # Plain pipes retain the same table layout without terminal escape sequences.
        console = self.console if self.progress is not None else Console(highlight=False)
        # One Rich render/write: the live refresh cannot split table and caption.
        console.print(Group(Text(''), Text(title, style='bold cyan'), Text(guide, style='dim'),
                            Text(''), table, *([Text(caption, style='dim')] if caption else [])))

    def flush_video_statistics(self):
        if not self.video_statistics:
            return
        records, self.video_statistics = self.video_statistics, []
        names = sorted({item.get('caption', '').split('\n')[0] for item in records})
        aliases = {name: f'C{index + 1}' for index, name in enumerate(names)}
        for stage in dict.fromkeys(item['stage'] for item in records):
            group = [item for item in records if item['stage'] == stage]
            rows = []
            for item in sorted(group, key=lambda item: item.get('caption', '')):
                name = item.get('caption', '').split('\n')[0]
                rows.extend([[aliases[name], *row] for row in item['rows']])
            caption = ('\n'.join(f'{aliases[name]} = {name}' for name in names)
                       if stage.endswith('video processing') else
                       'Fresh tracker calls only, milliseconds. SD = population SD; P05–P95 = central 90%.')
            self.numeric_table(stage, ['Camera', *group[0]['columns']], rows, caption)

    def milestone(self, timestamp, pipeline, label, detail, state, elapsed=None):
        duration = f' — reported interval {elapsed:.1f}s' if elapsed is not None else ''
        if state == 'Started':
            detail = COUNT.sub(lambda match: match.group(2), detail).replace(' frames processed', ' frames total')
            state = 'Stage'
        message = f'{timestamp} [{pipeline}] {state} | {label}: {detail}{duration}'
        if self.progress is not None:
            if state == 'Stage':
                self.console.print()
                self.console.rule(style='dim cyan')
            style = 'bold red' if state in ('Failed', 'Cancelled', 'Interrupted') else (
                'green' if state == 'Complete' else 'cyan' if state == 'Stage' else 'dim')
            self.console.print(message, style=style, markup=False)
        else:
            if state == 'Stage':
                print('\n' + '-' * 60, flush=True)
            encoding = sys.stdout.encoding or 'utf-8'
            print(message.encode(encoding, errors='backslashreplace').decode(encoding), flush=True)
        if state in ('Stage ended', 'Complete', 'Failed', 'Cancelled', 'Interrupted'):
            sample = self.rate_samples.get(pipeline)
            if sample and sample.get('average'):
                summary = f"  [{pipeline}] {sample['average']}  (observed interval)"
                if self.progress is not None:
                    self.console.print(summary, style='bold bright_cyan', markup=False)
                else:
                    print(summary, flush=True)
                # Preserve exactly one final rate summary for this counted stage.
                sample.pop('average')

    def feed(self, line: str):
        # Native tqdm bars can precede a logger record on the same physical line.
        record = re.search(r'\d{4}-\d\d-\d\d \d\d:\d\d:\d\d[,\.]\d+ (?:INFO|WARNING|ERROR) ', line)
        if record:
            line = line[record.start():]
        if 'Processing statistics: ' in line:
            try:
                result = json.loads(line.split('Processing statistics: ', 1)[1])
                if result['stage'].endswith((' | video processing', ' | tracker call time (ms)')):
                    self.video_statistics.append(result)
                    return
                if 'columns' in result:
                    self.numeric_table(result['stage'], result['columns'], result['rows'], result.get('caption', ''))
                else:
                    self.statistics(result['stage'], result['values'])
            except (ValueError, KeyError, TypeError, AttributeError):
                pass  # Unrecognized records remain available in the full log.
            else:
                return
        if 'Video processing summary: ' in line:
            # Full provenance stays in processing.log; numeric records supply the table.
            return
        match = EVENT.search(line)
        if match:
            pipeline, detail, state = match.groups()
            if pipeline == 'calibration' and state in ('complete', 'failed', 'cancelled'):
                self.flush_video_statistics()
            count = COUNT.search(detail)
            completed, total = map(int, count.groups()) if count else (0, None)
            if total == 0:
                total = None
            label = owner(pipeline, detail)
            stage = COUNT.sub('<count>', detail)
            # The initial camera-count suffix does not identify a different operation.
            stage = re.sub(r' \(\d+ cameras\)$', '', stage)
            stamp = re.search(r'\b\d\d:\d\d:\d\d\b', line)
            timestamp = stamp.group() if stamp else datetime.now().strftime('%H:%M:%S')
            source_time = re.search(r'\d{4}-\d\d-\d\d \d\d:\d\d:\d\d[,\.]\d+', line)
            now = (datetime.fromisoformat(source_time.group().replace(',', '.')).timestamp()
                   if source_time else datetime.now().timestamp())
            previous = self.history.get(pipeline)
            if state == 'running':
                if previous is None or previous['stage'] != stage:
                    if previous is not None and previous['state'] == 'running':
                        end_detail = previous['detail']
                        if COUNT.search(end_detail):
                            end_detail = f'Last progress report: {end_detail}'
                        self.milestone(timestamp, pipeline, previous['label'], end_detail,
                                       'Stage ended', now - previous['started'])
                    self.milestone(timestamp, pipeline, label, detail, 'Started')
                    self.history[pipeline] = dict(stage=stage, label=label, detail=detail,
                                                  started=now, state=state)
                else:
                    previous['detail'] = detail
            elif previous is None or previous['state'] != state:
                if previous is not None:
                    label = previous['label']
                summary = detail or (previous['detail'] if previous else pipeline)
                if previous and state == 'complete' and detail and detail != previous['detail']:
                    summary = f"{previous['detail']} — {detail}"
                self.milestone(timestamp, pipeline, label, summary, state.capitalize(),
                               now - previous['started'] if previous else None)
                self.history[pipeline] = dict(stage=stage, label=label, detail=summary,
                                              started=now, state=state)
            if self.progress is not None:
                if pipeline not in self.rows:
                    self.rows[pipeline] = self.progress.add_task(label, total=None, count='', detail='', rate='')
                task_id = self.rows[pipeline]
                if state == 'running' and self.stages.get(pipeline) != stage:
                    # Clear operation counts but retain elapsed time for the pipeline.
                    # Rich treats total=None in reset/update as "leave unchanged".
                    task = self.progress.tasks[task_id]
                    started = task.start_time
                    task.total = total
                    self.progress.reset(task_id, total=total)
                    task.start_time = started
                    self.stages[pipeline] = stage
                if state == 'running':
                    self.progress.update(task_id, description=label, completed=completed,
                                         count=f'{completed}/{total}' if total else '', detail=detail,
                                         rate=self.rate_text(pipeline, stage, detail, completed, total, now))
                if state == 'complete':
                    self.progress.update(task_id, total=1, completed=1, count='done', detail='Complete')
                if state in ('complete', 'failed', 'cancelled'):
                    self.progress.stop_task(task_id)
                if state in ('failed', 'cancelled'):
                    self.progress.update(task_id, description=label, count=state, detail=detail)
            return
        if (' ERROR ' in line or ' WARNING ' in line
                or 'Video processing summary:' in line or 'Video processing start:' in line):
            if self.progress is not None:
                self.console.print(line.strip(), style='red' if ' ERROR ' in line else (
                    'yellow' if ' WARNING ' in line else 'green'), markup=False)
            else:
                encoding = sys.stdout.encoding or 'utf-8'
                print(line.rstrip().encode(encoding, errors='backslashreplace').decode(encoding), flush=True)

    def __exit__(self, exc_type, exc_value, traceback):
        # Preserve partial or late-arriving camera results even on worker failure.
        self.flush_video_statistics()
        if exc_type:
            for pipeline, previous in self.history.items():
                if previous['state'] == 'running':
                    self.milestone(datetime.now().strftime('%H:%M:%S'), pipeline,
                                   previous['label'], previous['detail'], 'Interrupted',
                                   datetime.now().timestamp() - previous['started'])
        if self.progress is not None:
            for task in self.progress.tasks:
                if not task.finished:
                    self.progress.update(task.id, count=task.fields['count'] or ('stopped' if exc_type else ''),
                                         detail=task.fields['detail'])
                    self.progress.stop_task(task.id)
            self.progress.stop()
        if exc_type:
            message = f'Processing stopped. Full log: {self.log_path}'
            if self.console is not None:
                self.console.print(message, style='bold red', markup=False)
            else:
                print(message, file=sys.stderr, flush=True)
