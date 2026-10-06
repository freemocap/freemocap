"""Graph lab ASGI server: HTTP commands, one-way WebSocket reports, spawned workers.

Run: python -B -m experiments.executable_graph_lab.graph.server --output-root .test-artifacts/graph-ui-runs
"""
import argparse
import asyncio
from contextlib import asynccontextmanager, suppress
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
import uvicorn

from experiments.executable_graph_lab.graph.controller import Controller


class Reports:
    """Server cache and latest-only subscriber mailboxes, never worker acknowledgements."""
    def __init__(self):
        self.latest=None
        self.subscribers=set()

    def publish(self, value, revision):
        self.latest=json.dumps(dict(type='pipeline_state',revision=revision,value=value))
        for queue in tuple(self.subscribers):
            if queue.full(): queue.get_nowait()
            queue.put_nowait(self.latest)

    def subscribe(self):
        queue=asyncio.Queue(maxsize=1)
        self.subscribers.add(queue)
        if self.latest is not None: queue.put_nowait(self.latest)
        return queue


def create_app(output_root: Path, archive: Path | None = None):
    controller=Controller(output_root,archive)
    reports=Reports()
    command_lock=asyncio.Lock()  # server commands only; never shared with execution
    current=None

    async def collect_once():
        nonlocal current
        async with command_lock:
            await asyncio.to_thread(controller.refresh)
            if getattr(collect_once,'revision',-1)==controller.revision: return
            value=await asyncio.to_thread(controller.view)
            current=value
            collect_once.revision=controller.revision
        reports.publish(value,controller.revision)

    async def collect():
        while True:
            await collect_once()
            await asyncio.sleep(.1)

    @asynccontextmanager
    async def lifespan(app):
        await collect_once()
        collector=asyncio.create_task(collect())
        try: yield
        finally:
            collector.cancel()
            with suppress(asyncio.CancelledError): await collector
            await asyncio.to_thread(controller.close)

    app=FastAPI(title='FreeMoCap Graph Lab',lifespan=lifespan)
    app.state.controller=controller
    app.state.reports=reports

    @app.middleware('http')
    async def local_only(request: Request, call_next):
        # Prevent browser cross-site command requests and DNS rebinding.
        if request.url.hostname!='127.0.0.1':
            from fastapi.responses import JSONResponse
            return JSONResponse({'error':'Loopback host required'},status_code=403)
        if request.method=='POST' and request.headers.get('origin')!=str(request.base_url).rstrip('/'):
            from fastapi.responses import JSONResponse
            return JSONResponse({'error':'Same-origin commands required'},status_code=403)
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        return response

    async def body(request):
        data=await request.body()
        if len(data)>20000: raise HTTPException(413,'Request too large')
        try: value=json.loads(data)
        except ValueError as exc: raise HTTPException(400,'JSON required') from exc
        if not isinstance(value,dict): raise HTTPException(400,'Object required')
        return value

    @app.get('/')
    async def index(): return FileResponse(Path(__file__).parent/'web'/'index.html')

    @app.get('/api/catalog')
    async def catalog():
        return dict(read_only=False,real_runtime=True,transport='websocket',tasks=[dict(id='tracking',label='Real 2D tracking',description='Full recording. HTTP commands start a separate pipeline process; WebSocket reports display its progress.')])

    @app.get('/api/current')
    async def get_current(): return current

    @app.post('/api/preview')
    async def preview(request: Request):
        config=await body(request)
        async with command_lock:
            try: await asyncio.to_thread(controller.prepare,config)
            except (ValueError,OSError,TypeError,KeyError) as exc: raise HTTPException(400,str(exc)) from exc
        await collect_once()
        return current['graph']

    @app.post('/api/runs',status_code=202)
    async def start(request: Request):
        data=await body(request)
        if type(data.get('paused',False)) is not bool: raise HTTPException(400,'paused must be boolean')
        if data.get('held'): raise HTTPException(400,'Node holds are not supported')
        async with command_lock:
            try: await asyncio.to_thread(controller.start,data['config'],data.get('paused',False))
            except (ValueError,OSError,TypeError,KeyError) as exc: raise HTTPException(400,str(exc)) from exc
            run_id=controller.output.name
        return dict(accepted=True,run_id=run_id)

    @app.post('/api/runs/{run_id}/control',status_code=202)
    async def control(run_id: str, request: Request):
        data=await body(request)
        async with command_lock:
            try: controller.control(run_id,data['action'])
            except (ValueError,KeyError) as exc: raise HTTPException(409,str(exc)) from exc
        return dict(accepted=True,run_id=run_id,action=data['action'])

    @app.websocket('/websocket/connect')
    async def connect(socket: WebSocket):
        origin=socket.headers.get('origin')
        if socket.url.hostname!='127.0.0.1' or origin!=f'http://{socket.headers.get("host")}':
            await socket.close(code=1008)
            return
        await socket.accept()
        queue=reports.subscribe()
        async def sender():
            while True:
                payload=await queue.get()
                await asyncio.wait_for(socket.send_text(payload),timeout=2.)
        async def receiver():
            # No client messages command processing. This task only notices disconnects.
            while True:
                message=await socket.receive()
                if message['type']=='websocket.disconnect': return
                await socket.close(code=1008,reason='Use HTTP for commands')
                return
        tasks=[asyncio.create_task(sender()),asyncio.create_task(receiver())]
        try:
            done,_=await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
            for task in done: task.result()
        except (WebSocketDisconnect,TimeoutError,RuntimeError): pass
        finally:
            reports.subscribers.discard(queue)
            for task in tasks: task.cancel()
            for task in tasks:
                with suppress(asyncio.CancelledError,WebSocketDisconnect,RuntimeError): await task
    return app


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root',type=Path,required=True)
    parser.add_argument('--archive',type=Path)
    parser.add_argument('--port',type=int,default=8767)
    args=parser.parse_args()
    uvicorn.run(create_app(args.output_root.resolve(),args.archive.resolve() if args.archive else None),host='127.0.0.1',port=args.port)
