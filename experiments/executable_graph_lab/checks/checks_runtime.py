"""Graph scheduling contracts without models, recordings or device access."""
from concurrent.futures import CancelledError
from dataclasses import dataclass, replace
from threading import Event, Lock, Thread
import time
import unittest

from experiments.executable_graph_lab.graph.runtime import Binding, Executor, Node, Window, compile_plan
from experiments.executable_graph_lab.graph.inspector import project


@dataclass(frozen=True)
class Image:
    camera: str
    frame: int
    pixel_bytes: int = 100


class GraphRuntimeTests(unittest.TestCase):
    def test_elapsed_excludes_preview_and_freezes_at_completion(self):
        observed=[]
        run=Executor(self.plan(),dict(decode=lambda w,i:Image(w.camera,w.frame),track=lambda w,i:(),publish=lambda w,i:0),dict(io=3,gpu=1,cpu=1),observer=observed.append)
        run.started -= 1000
        self.assertEqual(run.snapshot()['elapsed_s'],0)
        run.run()
        elapsed=run.snapshot()['elapsed_s']
        self.assertLess(elapsed,10)
        self.assertEqual(run.snapshot()['elapsed_s'],elapsed)
        self.assertEqual(observed[-1]['status'],'complete')
        self.assertLess(len(observed),len(run.events))

    def test_recording_defaults_to_all_frames_without_test_cap(self):
        from unittest.mock import MagicMock, patch
        from pathlib import Path
        from experiments.executable_graph_lab.graph.tracking import inspect_recording, VideoMetadata
        group = MagicMock()
        group.frame_count = 2345
        group.video_metadata_by_id = {'camera': VideoMetadata.model_construct(frame_count=2345, end_frame=2345)}
        with patch('experiments.executable_graph_lab.graph.tracking.VideoGroupHelper.from_recording_path', return_value=group):
            context = inspect_recording(Path('recording'), 'videos')
            self.assertEqual(context.frames, 2345)
            self.assertEqual(context.videos['camera'].end_frame,2345)
            self.assertEqual(inspect_recording(Path('recording'), 'videos', 1000).frames, 1000)
            self.assertEqual(inspect_recording(Path('recording'), 'videos', 30).frames, 30)
        self.assertEqual(group.close.call_count, 3)

    def test_paused_run_admits_nothing_until_resume(self):
        run=Executor(self.plan(),dict(decode=lambda w,i:Image(w.camera,w.frame),track=lambda w,i:(),publish=lambda w,i:0),dict(io=3,gpu=1,cpu=1))
        run.paused.set()
        errors=[]
        def start():
            try: run.run()
            except BaseException as exc: errors.append(exc)
        thread=Thread(target=start)
        thread.start()
        try:
            time.sleep(.1)
            self.assertTrue(all(s=='pending' for s in run.states.values()))
            run.paused.clear()
            thread.join(3)
            self.assertFalse(thread.is_alive())
            self.assertFalse(errors)
            self.assertEqual(run.status,'complete')
        finally:
            run.cancelled.set()
            thread.join(3)

    def test_inspector_projects_actual_work_and_rejects_mixed_snapshots(self):
        p = self.plan()
        run = Executor(p,dict(decode=lambda w,i:Image(w.camera,w.frame),track=lambda w,i:(),publish=lambda w,i:0),dict(io=3,gpu=1,cpu=1))
        run.run()
        view = project(p.describe(),run.snapshot())
        self.assertFalse(view['graph']['synthetic'])
        self.assertTrue(view['graph']['read_only'])
        self.assertEqual(sum(n['counts']['complete'] for n in view['run']['nodes']),len(p.work))
        edges = view['graph']['partition_edges']
        self.assertEqual({e['source'] for e in edges if e['target']=='track'},{'decode@0','decode@1','decode@2'})
        self.assertEqual(next(e['inputs_per_item'] for e in edges if e['target']=='track'),3)
        with self.assertRaisesRegex(ValueError,'identity'):
            project(p.describe(),run.snapshot() | dict(graph_digest='wrong'))

    def plan(self):
        return compile_plan((
            Node('decode','Decode','camera_frame','io',Image,ordered=True,window=Window('track',2)),
            Node('track','Track','frame','gpu',tuple,(Binding('images','decode',Image,'all_sources'),),ordered=True),
            Node('publish','Publish','recording','cpu',int,(Binding('data','track',tuple,'sealed'),)),
        ),('a','b','c'),5)

    def test_graph_export_is_derived_from_executable_bindings(self):
        p = self.plan()
        edges = {(e['source'],e['target'],e['target_slot']) for e in p.describe()['edges']}
        actual = {(d.split('/')[0],w.node,port) for w in p.work for port,ids in w.inputs for d in ids}
        self.assertEqual(edges,actual)
        self.assertEqual(p.describe()['nodes'][0]['admission_window'],dict(consumer='track',frames=2))
        broken = (p.nodes[0],replace(p.nodes[1],inputs=(Binding('images','decode',str,'all_sources'),)),p.nodes[2])
        with self.assertRaisesRegex(ValueError,'payload'): compile_plan(broken,p.cameras,p.frames)

    def test_parallel_decoding_ordered_batches_and_bounded_retention(self):
        p = self.plan()
        lock, ready = Lock(), Event()
        arrivals, batches = [], []
        def decode(w,i):
            if w.frame==0:
                with lock:
                    arrivals.append(w.camera)
                    if len(arrivals)==3: ready.set()
                if not ready.wait(2): raise RuntimeError('Decoders did not overlap')
            return Image(w.camera,w.frame)
        def track(w,i):
            self.assertEqual([x.camera for x in i['images']],list(p.cameras))
            self.assertTrue(all(x.frame==w.frame for x in i['images']))
            batches.append(w.frame)
            time.sleep(.002)
            return (w.frame,)
        run = Executor(p,dict(decode=decode,track=track,publish=lambda w,i:len(i['data'])),dict(io=3,gpu=1,cpu=1))
        self.assertEqual(run.run()['publish'],5)
        self.assertEqual(batches,list(range(5)))
        self.assertLessEqual(run.peak_pixel_bytes,600)
        self.assertEqual(run.artifacts,{})

    def test_failure_drains_before_resource_cleanup(self):
        p, closed, ended = self.plan(),[],Event()
        run = None
        def decode(w,i):
            if w.camera=='a':
                run.own('io',lambda:closed.append(ended.is_set()))
                time.sleep(.02)
                ended.set()
            if w.camera=='b': raise RuntimeError('decoder failed')
            return Image(w.camera,w.frame)
        run = Executor(p,dict(decode=decode,track=lambda w,i:(),publish=lambda w,i:0),dict(io=3,gpu=1,cpu=1))
        with self.assertRaisesRegex(RuntimeError,'decoder failed'): run.run()
        self.assertEqual(closed,[True])
        self.assertEqual(run.status,'failed')
        self.assertNotIn('publish',run.results)

    def test_cancellation_does_not_close_an_active_device(self):
        entered, release, cancel, closed = Event(),Event(),Event(),[]
        errors = []
        run = None
        def track(w,i):
            run.own('gpu',lambda:closed.append(release.is_set()),owner=w)
            entered.set()
            release.wait(2)
            return ()
        run = Executor(self.plan(),dict(decode=lambda w,i:Image(w.camera,w.frame),track=track,publish=lambda w,i:0),
                       dict(io=3,gpu=1,cpu=1),cancelled=cancel)
        def start():
            try: run.run()
            except BaseException as e: errors.append(e)
        thread = Thread(target=start)
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            cancel.set()
            time.sleep(.07)
            self.assertFalse(closed)
        finally:
            release.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertIsInstance(errors[0],CancelledError)
        self.assertEqual(closed,[True])
        self.assertEqual(run.status,'cancelled')
        self.assertEqual(run.lifetimes[('track',None)],'closed')

    def test_declared_session_lifetime_ends_before_publication(self):
        p = self.plan()
        p = compile_plan((p.nodes[0],replace(p.nodes[1],lifetime_users=('track',)),p.nodes[2]),p.cameras,p.frames)
        closed = Event()
        run = None
        def track(w,i):
            if w.frame==0: run.own('gpu',closed.set,owner=w)
            return ()
        def publish(w,i):
            if not closed.wait(2): raise RuntimeError('Session cleanup gated behind publication')
            return 5
        run = Executor(p,dict(decode=lambda w,i:Image(w.camera,w.frame),track=track,publish=publish),dict(io=3,gpu=1,cpu=1))
        self.assertEqual(run.run()['publish'],5)
        self.assertEqual(run.lifetimes[('track',None)],'closed')

    def test_cleanup_failure_is_reported_and_other_handles_close(self):
        run, closed = None,[]
        def decode(w,i):
            if w.frame==0 and w.camera=='a':
                run.own('io',lambda:closed.append('first'))
                def broken(): raise RuntimeError('close failed')
                run.own('io',broken)
                run.own('io',lambda:closed.append('last'))
            return Image(w.camera,w.frame)
        run = Executor(self.plan(),dict(decode=decode,track=lambda w,i:(),publish=lambda w,i:0),dict(io=3,gpu=1,cpu=1))
        with self.assertRaisesRegex(RuntimeError,'close failed'): run.run()
        self.assertEqual(closed,['last','first'])
        self.assertEqual(run.status,'failed')


if __name__=='__main__': unittest.main()
