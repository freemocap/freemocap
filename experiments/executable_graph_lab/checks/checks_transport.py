"""Transport/process boundaries; no model weights or camera hardware required."""
import asyncio
import json
import multiprocessing as mp
import os
from pathlib import Path
import tempfile
import time
import unittest

from fastapi.testclient import TestClient
from experiments.executable_graph_lab.graph.runtime import Node, compile_plan
from experiments.executable_graph_lab.graph.worker import execute
from experiments.executable_graph_lab.graph.server import Reports, create_app


def isolated_worker(output, queue, cancelled, paused):
    plan=compile_plan((Node('compute','Compute','frame','cpu',int,ordered=True),),('a',),200)
    def handler(work, inputs):
        time.sleep(.002)
        return work.frame
    execute(plan,dict(compute=handler),dict(cpu=1),Path(output),queue,cancelled,paused)


class ProcessIsolationTests(unittest.TestCase):
    def test_worker_finishes_with_full_unconsumed_report_queue(self):
        ctx=mp.get_context('spawn')
        queue=ctx.Queue(maxsize=1)
        queue.put_nowait({'occupied':True})
        with tempfile.TemporaryDirectory() as directory:
            process=ctx.Process(target=isolated_worker,args=(directory,queue,ctx.Event(),ctx.Event()))
            process.start()
            process.join(30)
            try:
                self.assertFalse(process.is_alive(),'Undrained reports blocked execution or shutdown')
                self.assertEqual(process.exitcode,0)
                summary=json.loads((Path(directory)/'summary.json').read_text())
                self.assertEqual(summary['status'],'complete')
                self.assertEqual(summary['timings']['compute']['calls'],200)
                self.assertGreater(summary['dropped_reports'],0)
                self.assertNotEqual(summary['worker_pid'],os.getpid())
                self.assertEqual(len((Path(directory)/'events.jsonl').read_text().splitlines()),401)
            finally:
                if process.is_alive(): process.terminate();process.join()
                process.close()
        queue.close()

    def test_pause_and_cancel_are_explicit_control_signals(self):
        ctx=mp.get_context('spawn')
        queue=ctx.Queue(maxsize=2)
        paused,cancelled=ctx.Event(),ctx.Event()
        paused.set()
        with tempfile.TemporaryDirectory() as directory:
            process=ctx.Process(target=isolated_worker,args=(directory,queue,cancelled,paused))
            process.start()
            try:
                first=queue.get(timeout=30)['snapshot']
                self.assertTrue(first['paused'])
                self.assertEqual(first['timings']['compute']['calls'],0)
                cancelled.set()
                process.join(10)
                self.assertFalse(process.is_alive())
                summary=json.loads((Path(directory)/'summary.json').read_text())
                self.assertEqual(summary['status'],'cancelled')
                self.assertEqual(summary['timings']['compute']['calls'],0)
            finally:
                if process.is_alive(): process.terminate();process.join()
                process.close()
        queue.close()


class MailboxTests(unittest.IsolatedAsyncioTestCase):
    async def test_slow_subscriber_coalesces_and_reconnect_gets_latest(self):
        hub=Reports()
        slow=hub.subscribe()
        for revision in range(1000): hub.publish({'run':revision},revision)
        self.assertEqual(slow.qsize(),1)
        self.assertEqual(json.loads(await slow.get())['revision'],999)
        hub.subscribers.discard(slow)
        reconnect=hub.subscribe()
        self.assertEqual(json.loads(await reconnect.get())['value']['run'],999)


class HttpWebSocketTests(unittest.TestCase):
    def test_websocket_bootstrap_and_no_client_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            app=create_app(Path(directory))
            with TestClient(app,base_url='http://127.0.0.1') as client:
                self.assertIsNone(client.get('/api/current').json())
                self.assertEqual(client.get('/api/catalog').json()['transport'],'websocket')
                self.assertEqual(client.post('/api/runs',json={}).status_code,403)
                with client.websocket_connect('ws://127.0.0.1/websocket/connect',headers={'origin':'http://127.0.0.1'}) as ws:
                    self.assertEqual(ws.receive_json()['type'],'pipeline_state')
                    ws.send_json({'action':'start'})
                    self.assertEqual(ws.receive()['code'],1008)
                with client.websocket_connect('ws://127.0.0.1/websocket/connect',headers={'origin':'http://127.0.0.1'}) as ws:
                    self.assertEqual(ws.receive_json()['revision'],0)
                self.assertEqual(client.get('/api/runs/real').status_code,404)


if __name__=='__main__': unittest.main()
