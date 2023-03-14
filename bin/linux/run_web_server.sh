#!/usr/bin/env bash
#
# Start the webserver

# shellcheck disable=SC2086
gunicorn -b 0.0.0.0:8080 --timeout 0 -w 1 -k uvicorn.workers.UvicornWorker 'old_src.api.app_factory:create_app()'
#hypercorn 'old_src.api.app_factory:create_app()' --bind 0.0.0.0:8080 --websocket-ping-interval 1000
#uvicorn --factory old_src.api.app_factory:create_app --port 8080 --host 0.0.0.0 --workers 4
