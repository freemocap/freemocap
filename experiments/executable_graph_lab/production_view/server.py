"""Read-only local production graph inspector, separate from the application."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from .capture import capture

ROOT = Path(__file__).resolve().parent

def create_server(catalog, port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_GET(self):
            path = urlparse(self.path).path
            assets = {'/': ('viewer.html', 'text/html; charset=utf-8'),
                      '/viewer.js': ('viewer.js', 'text/javascript; charset=utf-8'),
                      '/layout.js': ('layout.js', 'text/javascript; charset=utf-8'),
                      '/style.css': ('style.css', 'text/css; charset=utf-8')}
            if path == '/api/catalog':
                raw, kind = json.dumps(catalog).encode(), 'application/json'
            elif path in assets:
                filename, kind = assets[path]
                raw = (ROOT / filename).read_bytes()
            else:
                self.send_error(404); return
            self.send_response(200)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(raw)
    return ThreadingHTTPServer(('127.0.0.1', port), Handler)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recording', type=Path, required=True)
    parser.add_argument('--calibration', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8768)
    args = parser.parse_args()
    catalog = capture(args.recording.resolve(strict=True), args.calibration.resolve(strict=True))
    server = create_server(catalog, args.port)
    print(f'Production definition viewer: http://127.0.0.1:{args.port}/ ({len(catalog["plans"])} variants)', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
