"""Server-owned run supervision. Processing lives exclusively in a spawned process."""
import json
import multiprocessing as mp
from pathlib import Path
from queue import Empty
from uuid import uuid4

from experiments.executable_graph_lab.graph.inspector import project
from experiments.executable_graph_lab.graph.worker import run_tracking


class Controller:
    def __init__(self, output_root, archive=None):
        self.output_root = output_root.resolve()
        self.ctx = mp.get_context('spawn')
        self.process = self.reports = self.plan = None
        self.latest = self.summary = self.definition = self.config = None
        self.output = None
        self.finished = False
        self.revision = 0
        if archive:
            self.definition=json.loads((archive/'graph.json').read_text())
            self.summary=json.loads((archive/'summary.json').read_text())
            self.latest=self.summary
            self.output=archive
            self.config=dict(recording=self.summary['source'],frames=None,video_subfolder='synchronized_videos')
            self.finished=True

    def busy(self):
        return self.process is not None and self.process.is_alive()

    def prepare(self, config):
        from experiments.executable_graph_lab.graph.tracking import inspect_recording, tracking_plan, PosthocMocapPipelineConfig
        if self.busy(): raise ValueError('Finish or cancel the current run before resolving another graph')
        if set(config) != {'recording','frames','video_subfolder'}: raise ValueError('Unknown or missing configuration fields')
        if config['frames'] is not None: raise ValueError('The real viewer processes full recordings; frames must be null')
        source=Path(config['recording']).expanduser().resolve(strict=True)
        folder=Path(config['video_subfolder'])
        if folder.is_absolute() or '..' in folder.parts: raise ValueError('Video subfolder must stay inside the recording')
        if source==self.output_root or source in self.output_root.parents: raise ValueError('Outputs must be outside the source recording')
        context=inspect_recording(source,str(folder))
        self.output=self.output_root/uuid4().hex
        self.destination=self.output/source.name
        self.context=context
        self.config=dict(config)
        self.plan=tracking_plan(context,self.destination)
        self.definition=self.plan.describe()
        self.task=PosthocMocapPipelineConfig(detector_type='rtmpose',charuco_tracking_enabled=False,
                                            video_fps=next(iter(context.videos.values())).fps)
        # Initial report only. The server never runs handlers or owns native sessions.
        self.latest=dict(status='created',paused=False,graph_digest=self.definition['digest'],elapsed_s=0.,
                         states={w.id:'pending' for w in self.plan.work},events=[],resource_lifetimes=[],
                         timings={n.id:dict(calls=0,seconds=0.,max_seconds=0.,first_started_s=None,last_finished_s=None) for n in self.plan.nodes})
        self.summary=None
        self.finished=False
        self.revision+=1

    def start(self, config, paused=False):
        if self.busy(): raise ValueError('A real run is already active')
        if config != self.config or self.latest is None or self.latest['status']!='created': self.prepare(config)
        if self.reports is not None: self.reports.close()
        if self.process is not None: self.process.close()
        self.destination.mkdir(parents=True,exist_ok=False)
        (self.output/'graph.json').write_text(json.dumps(self.definition,indent=2),encoding='utf-8')
        self.reports=self.ctx.Queue(maxsize=2)
        self.cancelled=self.ctx.Event()
        self.paused=self.ctx.Event()
        if paused: self.paused.set()
        self.process=self.ctx.Process(target=run_tracking,args=(self.context,self.task,self.destination,self.output,self.reports,self.cancelled,self.paused),name='GraphPipeline')
        self.latest=dict(self.latest,status='starting',paused=paused)
        self.process.start()
        self.revision+=1

    def refresh(self):
        """Background server collector; independent of requests and subscriber count."""
        changed=False
        if self.reports is not None:
            while True:
                try: report=self.reports.get_nowait()
                except Empty: break
                self.latest=report['snapshot']
                changed=True
        if self.process is not None and not self.busy() and not self.finished:
            self.process.join(timeout=0)
            path=self.output/'summary.json'
            if path.exists():
                self.summary=json.loads(path.read_text(encoding='utf-8'))
                self.latest=self.summary
            else:
                self.latest=dict(self.latest,status='failed',error=f'Worker exited with code {self.process.exitcode}; no final report. See worker.log.')
                self.latest['states']={k:'blocked' if v in ('pending','running') else v for k,v in self.latest['states'].items()}
            self.finished=True
            changed=True
        if changed: self.revision+=1
        return changed

    def view(self):
        if self.definition is None: return None
        value=project(self.definition,self.latest,self.summary)
        value['graph'].update(read_only=False,real_runtime=True)
        value['graph']['config'].update(self.config,frames=self.definition['frames'],task='tracking')
        if self.latest['status']=='created': value['run']=None
        else:
            value['run'].update(id=self.output.name,paused=self.latest.get('paused',False),
                output_directory=str(self.output),worker_pid=self.process.pid if self.process else self.latest.get('worker_pid'),
                diagnostic_error=self.latest.get('error'))
        return value

    def control(self, run_id, action):
        if self.output is None or run_id!=self.output.name: raise ValueError('Run identity mismatch')
        if not self.busy(): raise ValueError('No active run')
        if action=='pause': self.paused.set()
        elif action=='resume': self.paused.clear()
        elif action=='cancel': self.cancelled.set()
        else: raise ValueError('Unsupported command')
        # Commands do not masquerade as observed worker state.

    def close(self):
        if self.busy():
            self.cancelled.set()
            self.process.join()  # drain native calls on explicit server shutdown
        self.refresh()
        if self.reports is not None: self.reports.close()
