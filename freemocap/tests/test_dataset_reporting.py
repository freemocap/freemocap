"""Saved reporting faithfully renders available evidence without inventing values."""
from io import StringIO
from pathlib import Path
import unittest
from unittest.mock import patch

from freemocap.tools.datasets.reporting import render_report


class DatasetReportingTests(unittest.TestCase):
    def test_missing_evidence_is_not_success_or_zero(self):
        with patch.object(Path, 'is_file', return_value=False):
            text = render_report({}, log_path=Path('missing.log'), label='fixture')
        self.assertIn('not recorded', text)
        self.assertIn('Processing log unavailable', text)
        self.assertIn('does not revalidate', text)

    def test_existing_statistics_and_timing_survive_rendering(self):
        log = '\n'.join([
            'Detection throughput: 12.31 synchronized frames/s;',
            'detection.total | 1 | 90.0 | 90000 | 90000 | 0 | 90000',
            'INFO Processing statistics: {"stage":"Residuals","columns":["Camera","Mean"],"rows":[["C1",2.5]],"caption":"pixels"}',
            'INFO Processing statistics: malformed',
        ])
        with patch.object(Path, 'is_file', return_value=True), \
             patch.object(Path, 'open', return_value=StringIO(log)):
            text = render_report({'validation': {'frames': 222, 'finite_values': {'LANDMARKS_3D': 5}}},
                                 log_path=Path('fixture.log'), label='fixture')
        for expected in ('12.31', 'detection.total', '90000', 'Residuals', '2.5', 'pixels',
                         'finite_values.LANDMARKS_3D', '222', 'Unrecognized diagnostic records: 1'):
            self.assertIn(expected, text)


if __name__ == '__main__':
    unittest.main()


def test_current_bordered_performance_table_survives_summary(tmp_path):
    log = tmp_path / 'processing.log'
    log.write_text('''Posthoc performance [actual] outcome=complete; wall=207.318s
Completed detection: 1108 synchronized frames; 3324 camera images.
| Stage | Calls | Total (s) | Mean (ms) | First (ms) | After first (ms) | Max (ms) |
| graph.load_and_track | 1 | 176.356 | 176356.492 | 176356.492 | - | 176356.492 |
| inference.process_batch.images=3 | 1108 | 175.052 | 157.989 | 870.988 | 157.345 | 902.921 |
''')
    text = render_report({}, log_path=log, label='actual bordered format')
    assert 'graph.load_and_track' in text
    assert 'inference.process_batch.images=3' in text
    assert '157.345' in text
    assert 'Detailed operation timing: not recorded.' not in text


def test_structured_event_replaces_rounded_table_without_double_counting(caplog):
    import pytest
    from freemocap.core.pipeline.performance_report import PerformanceReport
    from freemocap.tools.datasets.reporting import parse_performance, normalized_stages
    report = PerformanceReport()
    report.frames, report.images = 2, 6
    report.record('batch', .123456789)
    report.record('batch', .01)
    with caplog.at_level('INFO'):
        report.log(pipeline_id='same', outcome='complete')
    parsed = parse_performance(caplog.text.splitlines())
    assert len(parsed) == 1
    assert parsed[0]['source'] == 'structured'
    stage = dict(normalized_stages(parsed[0]))['batch']
    assert stage['total_s'] == pytest.approx(.133456789, abs=1e-12)
    assert stage['mean_after_first_ms'] == pytest.approx(10)
    assert stage['amortized_ms_per_image'] == pytest.approx(133.456789 / 6)
    assert 'p95' not in stage


def test_worker_failure_retains_measured_phase(tmp_path, monkeypatch, caplog):
    import pytest
    from freemocap.tools.datasets import preparation
    from freemocap.tools.datasets.reporting import parse_performance
    def failing_worker(path, report):
        with report.measure('workflow.blender_preparation'):
            raise ValueError('fixture failure')
    monkeypatch.setattr(preparation, '_run_worker', failing_worker)
    with caplog.at_level('INFO'), pytest.raises(ValueError, match='fixture failure'):
        preparation.run_worker(tmp_path / 'request.json')
    report, = parse_performance(caplog.text.splitlines())
    assert report['outcome'] == 'failed'
    assert report['scope'] == 'dataset_worker'
    assert report['stages']['workflow.blender_preparation']['count'] == 1
    assert report['stages']['workflow.blender_preparation']['mean_after_first_ms'] is None


def test_frame_rates_and_costs_are_reciprocal_and_zero_span_has_no_rate():
    import pytest
    from freemocap.tools.datasets.reporting import normalized_stages
    report = dict(frames=2, images=6, stages={'work': dict(total_s=.25), 'empty': dict(total_s=0)})
    rows = dict(normalized_stages(report))
    assert rows['work']['amortized_ms_per_frame'] == 125
    assert rows['work']['synchronized_frames_per_second'] == 8
    assert rows['work']['amortized_ms_per_image'] == pytest.approx(1000 / 24)
    assert rows['work']['camera_images_per_second'] == 24
    assert rows['empty']['synchronized_frames_per_second'] is None
    assert rows['empty']['camera_images_per_second'] is None
