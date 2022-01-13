#!/usr/bin/env bash
#
# Run unit tests.

docker-compose run --rm app python -m pytest -p no:warnings ./
