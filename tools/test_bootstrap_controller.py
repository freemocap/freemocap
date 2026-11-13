import json
from pathlib import Path
import sys
import tempfile
import unittest
from bootstrap_controller import RoundController


class ControllerTests(unittest.TestCase):
    def test_completed_stage_is_not_repeated_and_tampering_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);controller=RoundController(root/'journal');output=root/'result.json'
            command=[sys.executable,'-c','import pathlib,sys;pathlib.Path(sys.argv[1]).write_text("{}")',str(output)]
            first=controller.run_stage('test-stage',command,root,output)
            self.assertEqual(controller.run_stage('test-stage',command,root,output),first)
            output.write_text('{"changed":true}')
            with self.assertRaises(ValueError):controller.run_stage('test-stage',command,root,output)

    def test_failed_stage_is_not_marked_complete(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);controller=RoundController(root/'journal')
            with self.assertRaises(Exception):controller.run_stage('bad',[sys.executable,'-c','raise SystemExit(2)'],root,root/'missing.json')
            self.assertEqual(json.loads((root/'journal/bad.json').read_text())['status'],'failed')
            with self.assertRaises(RuntimeError):controller.run_stage('bad',[],root,root/'missing.json')


if __name__=='__main__':unittest.main()
