#!/usr/bin/env bash
#
# Run docker container in bash shell session.

docker-compose run --rm --service-ports app bash
