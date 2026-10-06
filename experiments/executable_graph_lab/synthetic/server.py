"""Local-only standalone lab. Standard library only; no production imports."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse

from engine import Run
from graph import DEFAULTS, TASKS, compile_graph

ROOT = Path(__file__).resolve().parent
RUNS = {}
LOCK = Lock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass

    def send(self, status, body, content_type="application/json"):
        raw = json.dumps(body).encode() if content_type == "application/json" else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/": return self.send(200, (ROOT/"viewer.html").read_bytes(), "text/html; charset=utf-8")
        if path == "/api/catalog": return self.send(200, dict(defaults=DEFAULTS, tasks=TASKS))
        if path == "/api/current":
            with LOCK: run = next(reversed(RUNS.values()), None)
            return self.send(200, dict(graph=run.plan.describe(), run=run.snapshot()) if run else None)
        if path.startswith("/api/runs/"):
            with LOCK: run = RUNS.get(path.split("/")[-1])
            if run: return self.send(200, run.snapshot())
        self.send(404, dict(error="Not found"))

    def do_POST(self):
        # Browser mutations must originate from this loopback application.
        origin = self.headers.get("Origin")
        expected = f"http://{self.headers.get('Host')}"
        if origin and origin != expected:
            return self.send(403, dict(error="Cross-origin control is disabled"))
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self.send(415, dict(error="JSON required"))
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 20000: raise ValueError("Invalid request size")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict): raise ValueError("JSON object required")
            path = urlparse(self.path).path
            if path == "/api/preview":
                return self.send(200, compile_graph(body).describe())
            if path == "/api/runs":
                with LOCK:
                    if any(r.status not in ("complete", "partial", "failed", "cancelled") for r in RUNS.values()):
                        return self.send(409, dict(error="Cancel or finish the current run first"))
                    run = Run(body.get("config", {}), held=body.get("held", []), paused=body.get("paused", False))
                    RUNS[run.id] = run
                    while len(RUNS) > 6: RUNS.pop(next(iter(RUNS)))
                    run.start()
                return self.send(201, dict(graph=run.plan.describe(), run=run.snapshot()))
            if path.startswith("/api/runs/") and path.endswith("/control"):
                with LOCK: run = RUNS.get(path.split("/")[3])
                if not run: return self.send(404, dict(error="Run not found"))
                run.command(body.get("action"), body.get("node"))
                return self.send(200, run.snapshot())
            self.send(404, dict(error="Not found"))
        except (ValueError, TypeError, KeyError) as error:
            self.send(400, dict(error=str(error)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Graph Lab: http://127.0.0.1:{args.port}", flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        with LOCK:
            for run in RUNS.values():
                if run.status not in ("complete", "partial", "failed", "cancelled"):
                    run.command("cancel")
        server.server_close()
