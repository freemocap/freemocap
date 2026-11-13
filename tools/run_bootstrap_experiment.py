"""Run the approved bounded experiment through Tracker/Forge command interfaces."""
import argparse
import json
from pathlib import Path
from bootstrap_controller import RoundController, atomic_record


def main(config_path):
    config=json.loads(config_path.read_text());root=Path(config['project']);experiment=Path(config['experiment'])
    policy=json.loads((experiment/'experiment-policy.json').read_text())
    tracker=Path(config['tracker_tools']);forge=Path(config['forge_tools']);python=str(Path(config['python']))
    controller=RoundController(experiment/'journal')
    inputs=root/'datasets'/policy['starting_dataset'];best_run=Path(config['starting_run']);best_checkpoint=Path(config['starting_checkpoint'])
    baseline=json.loads(Path(config['starting_evaluation']).read_text())['by_epoch']['120']
    best_error=baseline['unfiltered']['mean_pixels'];history=[]
    def stage(name,script,arguments,completion,timeout=1800):
        command=[python,'-B',str(script),*map(str,arguments)]
        controller.run_stage(name,command,str(script.parent),str(completion),timeout=timeout)
        return json.loads(completion.read_text())
    for number in range(1,policy['maximum_rounds']+1):
        folder=experiment/f'round-{number:02d}';prefix=f'round-{number:02d}'
        common=['--project',root,'--experiment',experiment,'--round',number]
        selection=stage(prefix+'-mine',tracker/'mine_bootstrap_frames.py',common+['--run',best_run,'--checkpoint',best_checkpoint],folder/'mining/selection.json')
        if not selection['selected']:
            atomic_record(experiment/'experiment-result.json',{'status':'stopped','reason':'candidate_pool_exhausted','rounds':history});return
        stage(prefix+'-geometry',forge/'bootstrap_geometry.py',common+['--inputs',inputs],folder/'geometry/geometry-report.json')
        dataset=stage(prefix+'-merge',tracker/'merge_bootstrap_labels.py',common+['--inputs',inputs],folder/'dataset-report.json')
        if dataset['status']=='stopped':
            atomic_record(experiment/'experiment-result.json',{'status':'stopped','reason':dataset['reason'],'rounds':history});return
        inputs=Path(dataset['dataset']);run=folder/'training'
        training=stage(prefix+'-train',tracker/'train_bootstrap_round.py',['--inputs',inputs,'--run',run,'--checkpoint',best_checkpoint,'--epochs',policy['additional_epochs_per_round']],run/'training-report.json',timeout=3600)
        evaluation=stage(prefix+'-evaluate',tracker/'evaluate_bootstrap_round.py',common+['--previous-error',best_error],folder/'evaluation/evaluation-report.json')
        if evaluation['promote']:
            best_run=run;best_checkpoint=Path(evaluation['checkpoint']);best_error=evaluation['unfiltered']['mean_pixels']
        history.append({'round':number,'dataset':dataset['dataset'],'added_images':dataset['added_images'],
                        'training_report':str(run/'training-report.json'),'evaluation_report':str(folder/'evaluation/evaluation-report.json'),
                        'promoted':evaluation['promote'],'best_checkpoint':str(best_checkpoint),'best_mean_pixels':best_error})
        atomic_record(experiment/'round-state.json',{'rounds':history,'best_run':str(best_run),'best_checkpoint':str(best_checkpoint),
                      'best_mean_pixels':best_error,'next_round':number+1})
        print(json.dumps(history[-1]),flush=True)
    atomic_record(experiment/'experiment-result.json',{'status':'completed','reason':'approved_round_limit',
                  'rounds':history,'best_run':str(best_run),'best_checkpoint':str(best_checkpoint),'best_mean_pixels':best_error})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);a=p.parse_args();main(a.config)
