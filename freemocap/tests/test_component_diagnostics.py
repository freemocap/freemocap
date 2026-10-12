"""Diagnostic execution preserves bindings/failure propagation without overlap."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import threading
import unittest
from freemocap.tests.test_recording_executor import example_graph
from freemocap.tools.datasets.component_diagnostics import measure_isolated_components


class ComponentDiagnosticsTests(unittest.TestCase):
    def test_real_bindings_same_thread_and_report(self):
        with TemporaryDirectory() as folder:
            caller = threading.get_ident()
            seen = []
            def source(_):
                self.assertEqual(threading.get_ident(), caller)
                seen.append('source')
                return {'result': 42}
            def consume(inputs):
                self.assertEqual(threading.get_ident(), caller)
                self.assertIn('source', seen)
                self.assertEqual(inputs, {'result': 42})
                return inputs
            result = measure_isolated_components(graph=example_graph(), output=Path(folder),
                handlers={'source': source, 'annotation': consume, 'science': consume, 'save': consume})
            self.assertTrue(result.complete)
            report = json.loads((Path(folder)/'components.json').read_text())
            self.assertEqual(set(report['measurements']), set(result.outputs))
            self.assertFalse(report['profiled'])
            for entry in report['measurements'].values():
                self.assertGreaterEqual(entry['wall_seconds'], 0)
                self.assertGreaterEqual(entry['process_cpu_seconds'], 0)

    def test_failure_preserves_independent_branch_and_profile(self):
        with TemporaryDirectory() as folder:
            def fail(_):
                raise ValueError('scientific failure')
            result = measure_isolated_components(graph=example_graph(), output=Path(folder), profile=True,
                handlers={'source': lambda _: {'result': 42}, 'annotation': lambda x: x,
                          'science': fail, 'save': lambda _: self.fail('blocked handler ran')})
            self.assertIn('annotation', result.outputs)
            self.assertEqual(result.blocked['save'], ('science',))
            self.assertTrue((Path(folder)/'science.prof').is_file())
