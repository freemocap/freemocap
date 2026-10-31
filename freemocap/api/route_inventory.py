"""Inventory actual registered routes, including routes hidden from OpenAPI."""
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.routing import iter_route_contexts
from starlette.routing import WebSocketRoute


def write_route_inventory(app: FastAPI, output_path: str) -> None:
    route_records = []
    for route_context in iter_route_contexts(app.routes):
        route = route_context.original_route
        # Included WebSocket routes carry their prefixed path on the Starlette route.
        effective_route = getattr(route_context, 'starlette_route', None) or route_context
        route_records.append({
            "path": effective_route.path,
            "methods": ["WEBSOCKET"] if isinstance(route, WebSocketRoute) else sorted(getattr(route, "methods", [])),
            "name": route.name,
            "in_openapi": getattr(route, "include_in_schema", False),
        })
    Path(output_path).write_text(json.dumps(route_records, indent=2), encoding="utf-8")
