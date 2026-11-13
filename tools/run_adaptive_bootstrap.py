"""Resume the approved experiment at its explicit adaptive-policy boundary."""
import argparse
import json
from pathlib import Path
from bootstrap_controller import RoundController,atomic_record


def main(config_path):
    config=json.loads(config_path.read_text());root=Path(config['project']);experiment=Path(config['experiment'])
    tracker=Path(config['tracker_tools']);python=str(Path(config['python']));controller=RoundController(experiment/'journal')
    original=experiment/'round-02';dataset=json.loads((original/'dataset-report.json').read_text())
    previous=json.loads((original/'evaluation/evaluation-report.json').read_text())
    best_checkpoint=Path(previous['checkpoint']);best_run=original/'training';best_error=previous['unfiltered']['mean_pixels']
    history=json.loads((experiment/'round-state.json').read_text())['rounds']
    if [r['round'] for r in history]!=[1,2]:raise ValueError('Adaptive transition requires two completed original rounds')
    def stage(name,script,args,completion,timeout=3600):
        command=[python,'-B',str(script),*map(str,args)]
        controller.run_stage(name,command,str(script.parent),str(completion),timeout)
        return json.loads(completion.read_text())
    for number,folder in [(2,experiment/'round-02-extension'),(3,experiment/'round-03')]:
        folder.mkdir(exist_ok=True)
        if number==2:
            extension={**dataset,'added_images':0,'added_points':0,'old_points_quarantined':0,'decisions':[],
                       'note':'Same round-two dataset; training extension only'}
            target=folder/'dataset-report.json'
            if not target.exists():atomic_record(target,extension)
        else:
            # These candidates were mined before the extension, using epoch360.
            # Keep their recorded provenance; their geometry labels are independent.
            geometry=json.loads((folder/'geometry/geometry-report.json').read_text())
            if not geometry['events']:raise ValueError('No prepared round-three geometry')
            dataset=stage('round-03-merge',tracker/'merge_bootstrap_labels.py',
                          ['--project',root,'--experiment',experiment,'--round',3,'--inputs',Path(dataset['dataset'])],folder/'dataset-report.json')
            if dataset['status']!='completed':
                atomic_record(experiment/'experiment-result.json',{'status':'stopped','reason':dataset['reason'],'rounds':history});return
        run=folder/'training';prefix=folder.name
        trained=stage(prefix+'-adaptive-train',tracker/'train_adaptive_round.py',
                      ['--inputs',Path(dataset['dataset']),'--run',run,'--checkpoint',best_checkpoint,
                       '--reference-inputs',root/'datasets/training-inputs-v001','--previous-error',best_error,
                       '--policy',experiment/'adaptive-policy.json'],run/'training-report.json',timeout=7200)
        measured=stage(prefix+'-adaptive-evaluate',tracker/'finish_adaptive_round.py',
                       ['--project',root,'--stage',folder,'--round',number,'--previous-error',best_error],folder/'evaluation/evaluation-report.json')
        if measured['promote']:best_checkpoint=Path(measured['checkpoint']);best_run=run;best_error=measured['unfiltered']['mean_pixels']
        history.append({'round':number,'stage':prefix,'dataset':dataset['dataset'],'added_images':0 if number==2 else dataset['added_images'],
                        'training_report':str(run/'training-report.json'),'evaluation_report':str(folder/'evaluation/evaluation-report.json'),
                        'promoted':measured['promote'],'best_checkpoint':str(best_checkpoint),'best_mean_pixels':best_error,'stop_reason':trained['stop_reason']})
        atomic_record(experiment/'adaptive-state.json',{'rounds':history,'best_run':str(best_run),'best_checkpoint':str(best_checkpoint),'best_mean_pixels':best_error})
        print(json.dumps(history[-1]),flush=True)
    atomic_record(experiment/'experiment-result.json',{'status':'completed','reason':'three_rounds_with_approved_adaptive_extension',
                  'rounds':history,'best_run':str(best_run),'best_checkpoint':str(best_checkpoint),'best_mean_pixels':best_error})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);a=p.parse_args();main(a.config)
