#!/usr/bin/env bash
#
# Start docker services.

source bin/set_docker_runtime.sh

docker-compose up "$@"
