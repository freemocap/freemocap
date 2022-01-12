#!/usr/bin/env bash
#
# Run unit tests.
#
# -s                Show all output, do not capture
# -v                Verbose
# -q                Less verbose
# -x                Stop after first failure
# -l                Show local variables in tracebacks
# --lf              Only run tests that failed last run (or all if none failed)
# -k "expression"   Only run tests that match expession
# -r chars          Show extra test summary info as specified by chars:
#                   (f)failed,
#                   (E)error
#                   (s)skipped
#                   (x)failed
#                   (X)passed
#                   (w)pytest-warnings
#                   (p)passed
#                   (P)passed with output
#                   (a)all except (p) and (P)

docker-compose run --rm app python -m pytest -p no:warnings evaluator/tests/
