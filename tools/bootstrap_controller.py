"""File/CLI orchestration for bounded Tracker training and Forge geometry jobs.

No model inference, label fitting, or subjective acceptance decisions live here.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time


def atomic_record(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    handle,name=tempfile.mkstemp(prefix='.pending-',dir=path.parent)
    try:
        with os.fdopen(handle,'w',encoding='utf8') as stream:
            json.dump(value,stream,indent=2,allow_nan=False);stream.flush();os.fsync(stream.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


class RoundController:
    def __init__(self,root):
        self.root=Path(root).resolve()
        if 'worktrees' in [p.lower() for p in self.root.parts] or any((p/'.git').exists() for p in [self.root,*self.root.parents]):
            raise ValueError('Experiment state must be outside checkouts')
        self.root.mkdir(parents=True,exist_ok=True)

    def run_stage(self,name,command,working_directory,completion_file,timeout=1800):
        if not name.replace('-','').replace('_','').isalnum():raise ValueError('Invalid stage name')
        record=self.root/f'{name}.json';completion_file=Path(completion_file)
        if record.exists():
            previous=json.loads(record.read_text())
            if previous['status']=='complete':
                if previous['command']!=command or previous['completion_sha256']!=digest(completion_file):
                    raise ValueError('Completed stage inputs or output changed')
                return previous
            raise RuntimeError(f'Interrupted stage requires an explicit new attempt: {record}')
        state={'status':'running','command':command,'working_directory':str(working_directory),
               'completion_file':str(completion_file),'started_unix':time.time()}
        atomic_record(record,state)
        try:
            with (self.root/f'{name}.log').open('w',encoding='utf8') as log:
                subprocess.run(command,cwd=working_directory,stdout=log,stderr=subprocess.STDOUT,
                               timeout=timeout,check=True)
            json.loads(completion_file.read_text())
            state.update(status='complete',completion_sha256=digest(completion_file))
        except Exception as error:
            state.update(status='failed',error=f'{type(error).__name__}: {error}');raise
        finally:
            state['elapsed_seconds']=time.time()-state['started_unix'];atomic_record(record,state)
        return state


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True)
    a=p.parse_args();plan=json.loads(a.plan.read_text())
    controller=RoundController(plan['journal_directory'])
    for stage in plan['stages']:
        print(json.dumps(controller.run_stage(**stage)),flush=True)
