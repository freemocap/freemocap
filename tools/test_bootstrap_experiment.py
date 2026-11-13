import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from bootstrap_controller import atomic_record
from run_bootstrap_experiment import main


class ExperimentTests(unittest.TestCase):
    def test_three_rounds_retain_rejected_model_and_accumulate_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);experiment=root/'experiment';experiment.mkdir()
            atomic_record(experiment/'experiment-policy.json',{'starting_dataset':'start','maximum_rounds':3,'additional_epochs_per_round':120})
            atomic_record(root/'baseline.json',{'by_epoch':{'120':{'unfiltered':{'mean_pixels':6.}}}})
            atomic_record(root/'config.json',{'project':str(root),'experiment':str(experiment),'tracker_tools':str(root/'tracker'),
                          'forge_tools':str(root/'forge'),'python':'python','starting_run':str(root/'start-run'),
                          'starting_checkpoint':str(root/'start.pt'),'starting_evaluation':str(root/'baseline.json')})
            calls=[]
            def fake_stage(self,name,command,working_directory,completion_file,timeout):
                calls.append((name,command));number=int(name.split('-')[1]);action=name.split('-')[2]
                if action=='mine':value={'selected':[{}]}
                elif action=='merge':value={'status':'completed','dataset':str(root/f'data{number}'),'added_images':10}
                elif action=='evaluate':value={'promote':number!=2,'checkpoint':str(root/f'model{number}.pt'),'unfiltered':{'mean_pixels':6-number*.1}}
                else:value={}
                atomic_record(completion_file,value)
            with patch('run_bootstrap_experiment.RoundController.run_stage',fake_stage):main(root/'config.json')
            train_calls=[c for n,c in calls if n.endswith('-train')]
            self.assertEqual(train_calls[2][train_calls[2].index('--checkpoint')+1],str(root/'model1.pt'))
            self.assertEqual(train_calls[2][train_calls[2].index('--inputs')+1],str(root/'data3'))
            result=json.loads((experiment/'experiment-result.json').read_text())
            self.assertEqual(len(result['rounds']),3);self.assertEqual(result['status'],'completed')


if __name__=='__main__':unittest.main()
