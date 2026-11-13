"""Continue a corrected stopping decision without exceeding the original round budget."""
import argparse
import json
from pathlib import Path
from bootstrap_controller import RoundController,atomic_record


def main(config_path):
    config=json.loads(config_path.read_text());root=Path(config['project']);experiment=Path(config['experiment'])
    tracker=Path(config['tracker_tools']);python=str(Path(config['python']));controller=RoundController(experiment/'journal')
    original=experiment/'round-03';trained=json.loads((original/'training/training-report.json').read_text())
    base_policy=json.loads((experiment/'adaptive-policy.json').read_text())
    remaining=base_policy['maximum_additional_epochs']-trained['additional_epochs']
    if remaining<=0:raise ValueError('No approved round budget remains')
    final_record=experiment/'experiment-result.json';preserved=experiment/'experiment-result-before-continuation.json'
    if not preserved.exists():atomic_record(preserved,json.loads(final_record.read_text()))
    prior=json.loads(preserved.read_text());atomic_record(final_record,{**prior,'status':'running','reason':'corrected_plateau_continuation'})
    folder=experiment/'round-03-continuation';folder.mkdir(exist_ok=True)
    policy={**base_policy,'maximum_additional_epochs':remaining,'round_budget_already_consumed':trained['additional_epochs'],
            'round_budget_total':base_policy['maximum_additional_epochs'],
            'correction':'Training improvement after dataset expansion is independent of promotion against inherited model'}
    atomic_record(folder/'continuation-policy.json',policy)
    dataset=json.loads((original/'dataset-report.json').read_text())
    atomic_record(folder/'dataset-report.json',{**dataset,'added_images':0,'added_points':0,'old_points_quarantined':0,
                  'decisions':[],'note':'Same round-three dataset; continuation within its original300epochbudget'})
    checkpoint=Path(trained['last_checkpoint']);last=trained['history'][-1]
    atomic_record(original/'stopping-rule-correction.json',{'original_stop_epoch':trained['terminal_epoch'],
                  'reason':'The new dataset was improving at epoch640 but had not beaten its inherited model; that is not a plateau.',
                  'continue_from':str(checkpoint),'continuation_error':last['mean_pixels'],'remaining_epochs':remaining,
                  'preserved_prior_model':prior['best_checkpoint']})
    def stage(name,script,args,completion):
        controller.run_stage(name,[python,'-B',str(script),*map(str,args)],str(script.parent),str(completion),timeout=7200)
        return json.loads(completion.read_text())
    run=folder/'training'
    result=stage('round-03-continuation-adaptive-train',tracker/'train_adaptive_round.py',
                 ['--inputs',Path(dataset['dataset']),'--run',run,'--checkpoint',checkpoint,'--reference-inputs',root/'datasets/training-inputs-v001',
                  '--previous-error',last['mean_pixels'],'--policy',folder/'continuation-policy.json'],run/'training-report.json')
    if result['additional_epochs']+trained['additional_epochs']>base_policy['maximum_additional_epochs']:raise ValueError('Round budget exceeded')
    measured=stage('round-03-continuation-adaptive-evaluate',tracker/'finish_adaptive_round.py',
                   ['--project',root,'--stage',folder,'--round',3,'--previous-error',prior['best_mean_pixels']],folder/'evaluation/evaluation-report.json')
    if measured['promote']:
        prior.update(best_checkpoint=measured['checkpoint'],best_run=str(run),best_mean_pixels=measured['unfiltered']['mean_pixels'])
    prior['rounds'].append({'round':3,'stage':folder.name,'dataset':dataset['dataset'],'added_images':0,
                           'training_report':str(run/'training-report.json'),'evaluation_report':str(folder/'evaluation/evaluation-report.json'),
                           'promoted':measured['promote'],'best_checkpoint':prior['best_checkpoint'],'best_mean_pixels':prior['best_mean_pixels'],
                           'stop_reason':result['stop_reason'],'total_round_epochs':trained['additional_epochs']+result['additional_epochs']})
    atomic_record(final_record,{**prior,'status':'completed','reason':'three_rounds_with_corrected_adaptive_stopping'})
    print(json.dumps(prior['rounds'][-1]),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);a=p.parse_args();main(a.config)
