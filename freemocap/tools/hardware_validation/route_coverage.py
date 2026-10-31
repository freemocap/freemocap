"""Distinguish requested routes from assertions; never count an HTTP 200 as proof."""
import json
from pathlib import Path
import re


def write_route_coverage(output_directory: Path) -> None:
    inventory = json.loads((output_directory / 'route-inventory.json').read_text(encoding='utf-8'))
    request_path = output_directory / 'api-requests.jsonl'
    requests = [json.loads(line) for line in request_path.read_text(encoding='utf-8').splitlines()] if request_path.exists() else []
    records = []
    for route in inventory:
        pattern = re.sub(r'\{[^}]+\}', '[^/]+', route['path'])
        matching = [request for request in requests if request['method'] in route['methods']
                    and re.fullmatch(pattern, request['path'].split('?')[0])]
        records.append({**route, 'request_count': len(matching),
            'response_status_codes': sorted({request['status'] for request in matching}),
            'coverage': 'requested; inspect scenario assertions' if matching else 'not requested',
            'camera_suite_route': route['path'].startswith('/skellycam/camera/') or route['path'] in ('/health', '/shutdown', '/websocket/connect'),
        })
    (output_directory / 'route-coverage.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
