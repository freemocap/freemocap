#!/usr/bin/env bash
#
# Start the webserver

# shellcheck disable=SC2086
gunicorn -b 0.0.0.0:8080 -w 2 -k uvicorn.workers.UvicornWorker 'src.api.app_factory:create_app()'