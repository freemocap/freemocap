import json
import asyncio
from dataclasses import replace
from time import monotonic, sleep
import unittest

from engine import Artifact, Run, validate_outputs, validate_timing, validate_video_receipts
from graph import Binding, DiskFile, InputSlot, OutputSlot, compile_graph
from contracts import validate_payload
from lifecycle import SyntheticHandle


def wait_for(run, predicate, timeout=6):
    deadline = monotonic()+timeout
    while monotonic() < deadline:
        snapshot = run.snapshot()
        if predicate(snapshot): return snapshot
        sleep(.005)
    raise AssertionError(f"Timed out: {run.snapshot()}")


class GraphTests(unittest.TestCase):
    def test_payload_contract_rejects_wrong_fields_and_cpu_fallback(self):
        config = dict(family='RTMPose', pose_model='fixture:pose', person_model='fixture:person',
                      requested_provider='CUDAExecutionProvider', allow_cpu_fallback=False)
        validate_payload('detector_configuration', config)
        for bad in (config | dict(extra=True), config | dict(allow_cpu_fallback='false')):
            with self.assertRaisesRegex(ValueError, 'Invalid payload'):
                validate_payload('detector_configuration', bad)
        session = dict(session_id='test', configuration=config, camera_ids=[0], actual_provider='CPUExecutionProvider', live_handle=False)
        with self.assertRaisesRegex(ValueError, 'fallback policy'):
            validate_payload('inference_session', session)
        validate_payload('inference_session', session | dict(actual_provider='simulated'))
        with self.assertRaisesRegex(ValueError, 'Invalid payload'):
            validate_payload('video_frame', dict(frame=True, camera=0, timestamp=0, synthetic_image=True))

    def test_resource_cleanup_precedes_terminal_success(self):
        r = self.make_run()
        r.start()
        s = wait_for(r, lambda s: s['status']=='complete')
        self.assertEqual(len(s['resource_lifetimes']), 4)
        self.assertTrue(all(x['state']=='closed' for x in s['resource_lifetimes']))
        self.assertTrue(all(x['handle'].close_count==1 for x in r.owner.records.values()))

    def test_session_released_while_annotation_is_held(self):
        r = self.make_run()
        r.command('hold', 'encode')
        r.start()
        s = wait_for(r, lambda s: s['science_complete'])
        self.assertEqual(s['status'], 'running')
        self.assertEqual(r.owner.records['inference_session/all']['state'], 'closed')

    def test_resources_closed_on_handler_failure_and_cancellation(self):
        for action in ('failure', 'cancellation'):
            with self.subTest(action=action):
                r = self.make_run()
                if action=='failure': r.command('fail', 'pose')
                else: r.command('hold', 'pose')
                r.start()
                if action=='cancellation':
                    wait_for(r, lambda s: any(x['key']=='inference_session/all' for x in s['resource_lifetimes']))
                    r.command('cancel')
                s = wait_for(r, lambda s: s['status'] in ('failed','cancelled'))
                self.assertTrue(s['resource_lifetimes'])
                self.assertTrue(all(x['state']=='closed' for x in s['resource_lifetimes']))
                self.assertTrue(all(x['handle'].close_count==1 for x in r.owner.records.values()))

    def test_cleanup_failure_prevents_false_video_completion(self):
        class BrokenWriter(SyntheticHandle):
            async def close(self):
                self.close_count += 1
                raise RuntimeError('encoder flush failed')
        r = Run(dict(frames=2, compute_ms=0, annotation_ms=0),
                resource_factory=lambda key: BrokenWriter() if key.startswith('annotation_writer') else SyntheticHandle())
        self.addCleanup(lambda: self.stop(r))
        r.start()
        s = wait_for(r, lambda s: s['status']=='partial')
        self.assertTrue(s['science_complete'])
        self.assertNotIn('video_output/all/all', r.artifacts)
        self.assertTrue(any(x['state']=='cleanup_failed' for x in s['resource_lifetimes']))

    def test_cancel_during_close_waits_for_cleanup(self):
        class SlowWriter(SyntheticHandle):
            async def close(self):
                self.close_count += 1
                await asyncio.sleep(.08)
                self.closed = True
        r = Run(dict(frames=2, compute_ms=0, annotation_ms=0),
                resource_factory=lambda key: SlowWriter() if key.startswith('annotation_writer') else SyntheticHandle())
        self.addCleanup(lambda: self.stop(r))
        r.start()
        wait_for(r, lambda s: any(x['state']=='closing' and x['key'].startswith('annotation_writer') for x in s['resource_lifetimes']))
        r.command('cancel')
        s = wait_for(r, lambda s: s['status']=='cancelled')
        self.assertTrue(all(x['state']=='closed' for x in s['resource_lifetimes']))
        self.assertTrue(all(x['handle'].close_count==1 for x in r.owner.records.values()))

    def test_timing_and_publication_receipts_reject_invalid_data(self):
        timing = dict(camera_ids=[0], frame_numbers=[0, 1], timestamps_s=[0, .1])
        validate_timing(timing)
        for timestamps in ([0], [0, 0], [0, float('nan')]):
            with self.assertRaisesRegex(ValueError, 'timing'):
                validate_timing(timing | dict(timestamps_s=timestamps))
        receipts = [dict(camera=0, frame=f, stream_closed=f==1,
                         publication='simulated' if f==1 else 'pending', durable=False) for f in range(2)]
        validate_video_receipts(receipts, timing)
        for invalid in (receipts[:1], [receipts[0], receipts[0]]):
            with self.assertRaisesRegex(ValueError, 'Missing or duplicate'):
                validate_video_receipts(invalid, timing)
        with self.assertRaisesRegex(ValueError, 'close/publication'):
            validate_video_receipts([receipts[0], receipts[1] | dict(stream_closed=False)], timing)

    def test_session_is_required_but_does_not_gate_decoding(self):
        r = self.make_run(annotation=False)
        r.command('hold', 'session')
        r.start()
        wait_for(r, lambda s: next(n for n in s['nodes'] if n['id']=='decode')['state']=='complete')
        self.assertNotIn('pose/0/all', r.artifacts)
        r.command('release', 'session')
        wait_for(r, lambda s: s['status']=='complete')
        payload = json.loads(r.artifacts['pose/0/all']['out'].payload_json)
        self.assertEqual(payload['provider'], 'simulated')
        self.assertEqual(payload['batch_size'], 3)

    def test_calibration_failure_does_not_block_tracking_or_annotation(self):
        r = self.make_run()
        r.command('fail', 'calibration_load')
        r.start()
        s = wait_for(r, lambda s: s['status']=='failed')
        states = {n['id']: n['state'] for n in s['nodes']}
        self.assertEqual(states['pose'], 'complete')
        self.assertEqual(states['video_output'], 'complete')
        self.assertEqual(states['triangulate'], 'blocked')
        single = compile_graph(dict(cameras=1))
        self.assertNotIn('calibration_load', {n.id for n in single.nodes})

    def test_matching_waits_for_all_evidence_and_publication_has_provenance(self):
        p = compile_graph(dict(frames=4))
        geometry = next(w for w in p.work if w.node=='geometry')
        self.assertEqual(len(dict(geometry.inputs)['evidence']), 4)
        r = self.make_run()
        r.start()
        wait_for(r, lambda s: s['status']=='complete')
        receipt = json.loads(r.artifacts['science_output/all/all']['out'].payload_json)
        self.assertFalse(receipt['durable'])
        self.assertEqual(receipt['publication'], 'simulated')
        self.assertEqual(len(receipt['provenance']['data']), 4)

    def test_disk_declarations_in_every_variant(self):
        for task in ('mocap', 'pose', 'calibration'):
            for annotation in (False, True):
                for board in (False, True):
                    with self.subTest(task=task, annotation=annotation, board=board):
                        view = compile_graph(dict(task=task, annotation=annotation, board=board)).describe()
                        for node in view['nodes']:
                            self.assertEqual(bool(node['io_files']), node['io_role'] != 'none')

    def test_invalid_disk_contracts_are_rejected(self):
        plan = compile_graph({})
        def invalid(id, message, **changes):
            nodes = [replace(n, **changes) if n.id == id else n for n in plan.nodes]
            with self.assertRaisesRegex(ValueError, message): compile_graph({}, nodes)
        invalid('decode', 'declares no io_files', io_files=())
        invalid('recording', 'In-memory node', io_files=(DiskFile('C:/data/source.mp4', 'Source'),))
        for entry in (DiskFile('', 'Source'), DiskFile('C:/data/a.mp4', ''), DiskFile(None, 'Source'),
                      DiskFile('relative.mp4', 'Source'), DiskFile('C:/data/{unknown}.mp4', 'Source')):
            invalid('decode', 'Malformed io_files', io_files=(entry,))
        invalid('science_output', 'placeholder on non-camera', io_files=(DiskFile('C:/data/{camera}.parquet', 'Data'),))
        target = next(n for n in plan.nodes if n.id == 'encode').io_files[0].path
        invalid('science_output', 'Two nodes save', io_files=(DiskFile(target.replace('{camera}', '1'), 'Collision'),))
        # Duplicate literal declarations are rejected as well as template collisions.
        nodes = [replace(n, io_files=(DiskFile('C:/data/same.bin', 'Data'),)) if n.io_role=='write' else n for n in plan.nodes]
        with self.assertRaisesRegex(ValueError, 'Two nodes save'): compile_graph({}, nodes)

    def test_disk_paths_survive_partition_export_and_affect_identity(self):
        plan = compile_graph({})
        view = plan.describe()
        nodes = {n['id']: n for n in view['nodes']}
        for partition in view['partition_nodes']:
            self.assertEqual(partition['io_files'], nodes[partition['logical_id']]['io_files'])
        modified = [replace(n, io_files=(DiskFile(n.io_files[0].path+'.changed', n.io_files[0].contents),)) if n.id=='science_output' else n for n in plan.nodes]
        self.assertNotEqual(plan.digest, compile_graph({}, modified).digest)

    def test_annotation_has_exactly_one_video_writer(self):
        nodes = {n.id: n for n in compile_graph({}).nodes}
        self.assertEqual(nodes['encode'].io_role, 'write')
        self.assertEqual(nodes['video_output'].io_role, 'none')
        self.assertFalse(nodes['video_output'].io_files)
        # Both read nodes intentionally reference the same source, which is valid.
        self.assertEqual(nodes['decode'].io_files, nodes['annotation_decode'].io_files)
        paths = [f.path for n in nodes.values() if n.io_role=='write' for f in n.io_files]
        self.assertEqual(len(paths), len(set(paths)))

    def make_run(self, **kwargs):
        run = Run(dict(frames=4, compute_ms=1, annotation_ms=1, **kwargs))
        self.addCleanup(lambda: self.stop(run))
        return run

    @staticmethod
    def stop(run):
        if run.status not in ("complete", "partial", "failed", "cancelled"):
            run.command("cancel")
        if run.thread: run.thread.join(2)

    def test_definitions_and_execution_inputs_have_identical_edges(self):
        p = compile_graph({})
        displayed = {(e["source"], e["target"], e["port"]) for e in p.describe()["edges"]}
        resolved = {(key.split('/')[0], w.node, port) for w in p.work for port, keys in w.inputs for key in keys}
        self.assertEqual(displayed, resolved)
        nodes = {n.id: n for n in p.nodes}
        for edge in p.describe()['edges']:
            producer = next(s for s in nodes[edge['source']].outputs if s.name == edge['source_slot'])
            consumer = next(s for s in nodes[edge['target']].input_slots if s.name == edge['target_slot'])
            self.assertEqual(producer.data_type, consumer.data_type)

    def test_cycles_types_and_keys_rejected(self):
        p = compile_graph({})
        nodes = list(p.nodes)
        nodes[0] = replace(nodes[0], inputs=(Binding("bad", "decode", "video_frame", "sealed"),), input_slots=(InputSlot("bad", "video_frame"),))
        with self.assertRaisesRegex(ValueError, "cycle"): compile_graph({}, nodes)
        nodes = list(p.nodes)
        index = next(i for i, n in enumerate(nodes) if n.id=='decode')
        nodes[index] = replace(nodes[index], inputs=(Binding("recording", "recording", "wrong", "broadcast"), *nodes[index].inputs[1:]))
        with self.assertRaisesRegex(ValueError, "port type"): compile_graph({}, nodes)
        nodes[index] = replace(nodes[index], inputs=(Binding("recording", "recording", "recording_context", "same_key"), *nodes[index].inputs[1:]))
        with self.assertRaisesRegex(ValueError, "key binding"): compile_graph({}, nodes)

    def test_required_optional_and_named_output_contracts(self):
        p = compile_graph({})
        nodes = list(p.nodes)
        decode = next(i for i,n in enumerate(nodes) if n.id == 'decode')
        nodes[decode] = replace(nodes[decode], inputs=())
        with self.assertRaisesRegex(ValueError, 'Required input'): compile_graph({}, nodes)
        nodes = list(p.nodes)
        nodes[decode] = replace(nodes[decode], inputs=(replace(nodes[decode].inputs[0], source_slot='missing'), *nodes[decode].inputs[1:]))
        with self.assertRaisesRegex(ValueError, 'port type'): compile_graph({}, nodes)
        r = self.make_run(board=False, annotation=False)
        r.start()
        wait_for(r, lambda s: s['status'] == 'complete')
        obs = next(n for n in r.plan.nodes if n.id == 'observations')
        self.assertFalse(next(s for s in obs.input_slots if s.name == 'boards').required)
        self.assertFalse(any(b.port == 'boards' for b in obs.inputs))
        self.assertEqual(json.loads(r.artifacts['observations/0/all']['out'].payload_json)['boards'], 0)
        connected = self.make_run()
        connected.command('hold', 'board')
        connected.start()
        wait_for(connected, lambda s: next(n for n in s['nodes'] if n['id']=='pose')['state']=='complete')
        self.assertNotIn('observations/0/all', connected.artifacts)
        connected.command('release', 'board')
        wait_for(connected, lambda s: s['status']=='complete')

    def test_output_slot_publication_is_validated(self):
        p = compile_graph({})
        n, w = p.nodes[0], p.work[0]
        with self.assertRaisesRegex(ValueError, 'output slots'):
            validate_outputs(n, w, {'wrong': Artifact('recording', w.id, '{}')})
        with self.assertRaisesRegex(ValueError, 'type'):
            validate_outputs(n, w, {'out': Artifact('image', w.id, '{}')})
        multi = replace(n, outputs=(OutputSlot('a', 'recording'), OutputSlot('b', 'image')))
        validate_outputs(multi, w, {'a': Artifact('recording', w.id, '{}'), 'b': Artifact('image', w.id, '{}')})

    def test_partition_view_matches_resolved_work_and_cardinality(self):
        for cameras in (1, 3, 4):
            for task in ('mocap', 'pose', 'calibration'):
                plan = compile_graph(dict(cameras=cameras, frames=3, task=task))
                view = plan.describe()
                by_id = {w.id: w for w in plan.work}
                def partition(w): return f'{w.node}@{w.camera}' if w.camera is not None else w.node
                actual = {(partition(by_id[s]), partition(w), port) for w in plan.work
                          for port, sources in w.inputs for s in sources}
                shown = {(e['source'], e['target'], e['port']) for e in view['partition_edges']}
                self.assertEqual(actual, shown)
                board = next(n for n in view['nodes'] if n['id'] == 'board')
                self.assertEqual(board['partition_count'], cameras)
                if task != 'calibration':
                    fanin = next(e for e in view['edges'] if e['id'] == 'pose:images')
                    self.assertEqual(fanin['inputs_per_item'], cameras)
                self.assertEqual(next(n for n in view['nodes'] if n['id'] == 'decode')['io_role'], 'read')
                self.assertEqual(next(n for n in view['nodes'] if n['id'] == 'science_output')['io_role'], 'write')

    def test_partition_progress_sums_to_logical_progress(self):
        r = self.make_run()
        r.start()
        snapshot = wait_for(r, lambda s: s['status'] == 'complete')
        for logical in snapshot['nodes']:
            partitions = [n for n in snapshot['partition_nodes'] if n['logical_id'] == logical['id']]
            if partitions:
                self.assertEqual(sum(n['counts']['complete'] for n in partitions), logical['counts']['complete'])

    def test_all_task_variants_and_branch_options(self):
        for task in ("mocap", "pose", "calibration"):
            for annotation in (False, True):
                with self.subTest(task=task, annotation=annotation):
                    r = self.make_run(task=task, annotation=annotation)
                    r.start()
                    s = wait_for(r, lambda s: s["status"] in ("complete", "partial", "failed"))
                    self.assertEqual(s["status"], "complete")
                    self.assertTrue(s["science_complete"])

    def test_held_annotation_does_not_gate_science(self):
        r = Run(dict(frames=8, compute_ms=2, annotation_ms=1), held=["encode"])
        self.addCleanup(lambda: self.stop(r))
        r.start()
        s = wait_for(r, lambda s: s["science_complete"])
        self.assertEqual(s["status"], "running")
        encode = next(n for n in s["nodes"] if n["id"] == "encode")
        self.assertEqual(encode["counts"].get("complete", 0), 0)
        self.assertIn("held by user", encode["reasons"])
        r.command("release", "encode")
        wait_for(r, lambda s: s["status"] == "complete")

    def test_pause_step_cancel(self):
        r = Run(dict(frames=3, compute_ms=3), paused=True)
        self.addCleanup(lambda: self.stop(r))
        r.start()
        wait_for(r, lambda s: s["status"] == "running")
        self.assertEqual(r.snapshot()["artifacts"], 0)
        r.command("step")
        wait_for(r, lambda s: s["artifacts"] == 1)
        sleep(.025)
        self.assertEqual(r.snapshot()["artifacts"], 1)
        r.command("cancel")
        s = wait_for(r, lambda s: s["status"] == "cancelled")
        sleep(.025)
        self.assertEqual(s["artifacts"], r.snapshot()["artifacts"])

    def test_derived_failure_preserves_science(self):
        r = self.make_run()
        r.command("fail", "encode")
        r.start()
        s = wait_for(r, lambda s: s["status"] == "partial")
        self.assertTrue(s["science_complete"])
        self.assertTrue(any(n["state"] == "failed" for n in s["nodes"]))

    def test_science_failure_blocks_dependents(self):
        r = self.make_run()
        r.command("fail", "pose")
        r.start()
        s = wait_for(r, lambda s: s["status"] == "failed")
        self.assertFalse(s["science_complete"])
        self.assertEqual(next(n for n in s["nodes"] if n["id"] == "science_output")["state"], "blocked")

    def test_ordered_streams_and_batched_hydration(self):
        r = self.make_run(annotation=False)
        r.start()
        wait_for(r, lambda s: s["status"] == "complete")
        for f in range(4):
            value = json.loads(r.artifacts[f"pose/{f}/all"]["out"].payload_json)
            self.assertEqual(value["batch_size"], 3)
        events = list(r.events)
        for n in r.plan.nodes:
            if not n.ordered: continue
            for w in r.plan.work:
                if w.node != n.id or not w.predecessor: continue
                prior = next((e["sequence"] for e in events if e["kind"] == "completed" and e["detail"] == w.predecessor), None)
                dispatch = next((e["sequence"] for e in events if e["kind"] == "dispatched" and e["detail"] == w.id), None)
                if prior is not None and dispatch is not None: self.assertLess(prior, dispatch)


if __name__ == "__main__": unittest.main(verbosity=2)
