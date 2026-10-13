"""Execution reports retain failures without claiming scientific acceptance."""
import copy
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from freemocap.tools.datasets.execution import measure_worker, require_implementation


class DatasetExecutionTests(unittest.TestCase):
    def test_cli_and_preflight_select_graph(self):
        from freemocap.tools.datasets.__main__ import parser
        from freemocap.tools.datasets import workflow
        args = parser().parse_args(['process', 'test_data', '--implementation', 'graph'])
        self.assertEqual(args.implementation, 'graph')
        self.assertEqual(parser().parse_args(['process-all']).implementation, 'graph')
        with patch.object(workflow, 'checked_ready', return_value=None):
            plan = workflow.preflight('test_data', recordings_root=Path('raw'),
                                      prepared_root=Path('prepared'), implementation=args.implementation)
            self.assertEqual(plan['implementation'], 'graph')

    def test_selection_never_falls_back(self):
        self.assertEqual(require_implementation('current'), 'current')
        self.assertEqual(require_implementation('graph'), 'graph')
        for value in ('typo',):
            with self.subTest(value=value), self.assertRaises(ValueError):
                require_implementation(value)

    def test_graph_restart_is_rejected_before_reading_saved_files(self):
        from freemocap.tools.datasets import workflow
        with patch.object(workflow, 'checked_ready') as ready:
            with self.assertRaisesRegex(ValueError, 'saved-stage restart'):
                workflow.preflight('test_data', recordings_root=Path('raw'),
                    prepared_root=Path('prepared'), implementation='graph', start='reconstruction')
            ready.assert_not_called()

    def run_measured(self, error=None):
        writes = []
        with patch('freemocap.tools.datasets.execution.write_json',
                   side_effect=lambda path, report: writes.append(copy.deepcopy(report))), \
             patch('freemocap.tools.datasets.execution.perf_counter', side_effect=[10.0, 12.5]):
            try:
                with measure_worker(report_path=Path('performance.json'),
                                    implementation='current', operation='process') as report:
                    if error:
                        raise error
            except BaseException as caught:
                self.assertIs(caught, error)
        return report, writes

    def test_success_has_measured_scope_but_no_acceptance_claim(self):
        report, writes = self.run_measured()
        self.assertEqual([item['status'] for item in writes], ['running', 'complete'])
        self.assertEqual(report['elapsed_s'], 2.5)
        self.assertEqual(report['scope'], 'worker_lifecycle')
        self.assertNotIn('accepted', report)

    def test_failure_timeout_and_interrupt_are_retained(self):
        for error, status in [(RuntimeError('failed'), 'failed'),
                              (subprocess.TimeoutExpired('worker', 1), 'timeout'),
                              (KeyboardInterrupt(), 'interrupted')]:
            with self.subTest(status=status):
                report, writes = self.run_measured(error)
                self.assertEqual(report['status'], status)
                self.assertEqual(report['error']['type'], type(error).__name__)
                self.assertEqual(writes[-1]['elapsed_s'], 2.5)

    def test_unavailable_implementation_does_not_write_report(self):
        with patch('freemocap.tools.datasets.execution.write_json') as write:
            with self.assertRaises(ValueError):
                with measure_worker(report_path=Path('performance.json'),
                                    implementation='typo', operation='process'):
                    self.fail('Unavailable execution started')
            write.assert_not_called()


if __name__ == '__main__':
    unittest.main()
