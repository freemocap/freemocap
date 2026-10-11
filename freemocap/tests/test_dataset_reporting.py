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
        for expected in ('12.31', 'detection.total', '90.0', 'Residuals', '2.5', 'pixels',
                         'finite_values.LANDMARKS_3D', '222', 'Unrecognized diagnostic records: 1'):
            self.assertIn(expected, text)


if __name__ == '__main__':
    unittest.main()
