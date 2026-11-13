import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from bootstrap_controller import atomic_record
from run_adaptive_bootstrap import main


class AdaptiveIntegrationTests(unittest.TestCase):
    def test_extension_reuses_dataset_then_round_three_uses_selected_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);exp=root/'experiment'
            atomic_record(exp/'round-02/dataset-report.json',{'dataset':str(root/'data2'),'added_images':35})
            atomic_record(exp/'round-02/evaluation/evaluation-report.json',{'checkpoint':str(root/'model2.pt'),'unfiltered':{'mean_pixels':3.5}})
            atomic_record(exp/'round-03/geometry/geometry-report.json',{'events':[{}]})
            atomic_record(exp/'round-state.json',{'rounds':[{'round':1},{'round':2}]})
            atomic_record(root/'config.json',{'project':str(root),'experiment':str(exp),'tracker_tools':str(root/'tracker'),'python':'python'})
            calls=[]
            def fake(self,name,command,working_directory,completion_file,timeout):
                calls.append((name,command))
                if name.endswith('merge'):result={'status':'completed','dataset':str(root/'data3'),'added_images':30}
                elif name.endswith('train'):result={'stop_reason':'validation_plateau'}
                elif 'extension' in name:result={'promote':True,'checkpoint':str(root/'extended.pt'),'unfiltered':{'mean_pixels':3.1}}
                else:result={'promote':False,'checkpoint':str(root/'model3.pt'),'unfiltered':{'mean_pixels':3.2}}
                atomic_record(completion_file,result)
            with patch('run_adaptive_bootstrap.RoundController.run_stage',fake):main(root/'config.json')
            commands={name:cmd for name,cmd in calls}
            first=commands['round-02-extension-adaptive-train'];last=commands['round-03-adaptive-train']
            self.assertEqual(first[first.index('--inputs')+1],str(root/'data2'))
            self.assertEqual(last[last.index('--inputs')+1],str(root/'data3'))
            self.assertEqual(last[last.index('--checkpoint')+1],str(root/'extended.pt'))
            result=json.loads((exp/'experiment-result.json').read_text())
            self.assertEqual(result['best_checkpoint'],str(root/'extended.pt'))


if __name__=='__main__':unittest.main()
