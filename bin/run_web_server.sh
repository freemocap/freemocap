#!/usr/bin/env bash
#
# Start the webserver

# shellcheck disable=SC2086
gunicorn -b 0.0.0.0:8080 --timeout 0 -w 1 -k uvicorn.workers.UvicornWorker 'src.api.app_factory:create_app()'