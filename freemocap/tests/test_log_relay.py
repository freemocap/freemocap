"""The IPC consumer outlives websocket clients and producer joins."""
import multiprocessing
import logging
import os
from queue import Queue, Full

import pytest
from freemocap.api.websocket.log_relay import LogRelay


def test_worker_logs_reach_main_file_without_frontend(tmp_path):
    path = tmp_path / 'application.log'
    handler = logging.FileHandler(path)
    root = logging.getLogger()
    root.addHandler(handler)
    source = Queue()
    relay = LogRelay(source)
    relay.start()
    try:
        record = logging.LogRecord('worker', logging.ERROR, __file__, 1, 'failure %s', ('detail',), None)
        payload = dict(record.__dict__, process=os.getpid() + 1,
                       message='failure detail', exc_info='Serialized traceback', exc_text=None)
        source.put(payload)
        relay.stop()
        handler.flush()
        assert path.read_text() == 'failure detail\nSerialized traceback\n'
    finally:
        relay.stop()
        root.removeHandler(handler)
        handler.close()


def test_main_records_are_not_written_twice_or_requeued(tmp_path):
    path = tmp_path / 'application.log'
    handler = logging.FileHandler(path)
    root = logging.getLogger()
    root.addHandler(handler)
    source = Queue()
    relay = LogRelay(source)
    relay.start()
    try:
        record = logging.LogRecord('main', logging.ERROR, __file__, 1, 'main message', (), None)
        handler.handle(record)
        payload = dict(record.__dict__, message='main message')
        with relay.subscribe() as first, relay.subscribe() as second:
            source.put(payload)
            assert first.get(timeout=2) == second.get(timeout=2) == payload
        relay.stop()
        handler.flush()
        assert path.read_text() == 'main message\n'
        assert relay.received == 1
    finally:
        relay.stop()
        root.removeHandler(handler)
        handler.close()


def produce(queue):
    for index in range(80):
        queue.put({'message': 'x' * 100000, 'index': index})


def test_spawned_producer_exits_without_frontend():
    context = multiprocessing.get_context('spawn')
    source = context.Queue(maxsize=100)
    relay = LogRelay(source)
    relay.start()
    producer = context.Process(target=produce, args=(source,))
    producer.start()
    try:
        producer.join(timeout=15)
        assert producer.exitcode == 0, 'IPC feeder could not finish without a frontend'
        relay.stop()
        assert relay.received == 80
        assert relay.dropped_without_clients == 80
    finally:
        if producer.is_alive():
            producer.terminate()
            producer.join(timeout=5)
        if producer.exitcode == 0:
            relay.stop()
            source.close()
            source.join_thread()


def test_fanout_disconnect_reconnect_and_slow_client():
    source = Queue()
    relay = LogRelay(source, client_backlog=2)
    relay.start()
    try:
        with relay.subscribe() as slow, relay.subscribe() as fast:
            for index in range(20):
                source.put({'index': index})
                assert fast.get(timeout=2) == {'index': index}
            assert [slow.get_nowait(),slow.get_nowait()] == [{'index':18},{'index':19}]
            assert relay.dropped_slow_clients == 18
        source.put({'index':20})
        # Sentinel stops only after all earlier records were consumed, no qsize polling.
        relay.stop()
        assert relay.dropped_without_clients == 1
    finally:
        relay.stop()


def test_two_clients_receive_identical_records_and_reconnect():
    relay=LogRelay(Queue());relay.start()
    try:
        with relay.subscribe() as first, relay.subscribe() as second:
            relay._source.put({'message':'both'})
            assert first.get(timeout=2)==second.get(timeout=2)=={'message':'both'}
        with relay.subscribe() as reconnected:
            relay._source.put({'message':'new'})
            assert reconnected.get(timeout=2)=={'message':'new'}
    finally:
        relay.stop()


def test_reader_error_surfaces_to_supervisor():
    class BrokenQueue:
        def get(self):raise OSError('broken IPC')
    relay=LogRelay(BrokenQueue());relay.start();relay._thread.join(timeout=2)
    with pytest.raises(RuntimeError,match='reader failed') as error:
        relay.check_health()
    assert isinstance(error.value.__cause__,OSError)


def test_stop_can_retry_if_sentinel_submission_fails():
    class OnceFull(Queue):
        first=True
        def put(self,item,*args,**kwargs):
            if self.first:
                self.first=False
                raise Full
            return super().put(item,*args,**kwargs)
    relay=LogRelay(OnceFull());relay.start()
    with pytest.raises(Full):relay.stop()
    relay.stop()
    assert not relay._thread.is_alive()
