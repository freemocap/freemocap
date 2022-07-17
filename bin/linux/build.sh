#!/usr/bin/env bash
#
# Run tests meant to run in CI

# https://github.com/moby/moby/issues/39003#issuecomment-852915070 - use buildkit inline cache with --build-arg (in docker-compose file)
COMPOSE_DOCKER_CLI_BUILD=1 DOCKER_BUILDKIT=1 docker-compose build
