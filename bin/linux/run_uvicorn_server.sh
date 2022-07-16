#!/usr/bin/env bash
#
# Start the webserver


uvicorn --factory src.api.app_factory:create_app --port 8080 --host 0.0.0.0 --workers 8 --ws websockets --reload


