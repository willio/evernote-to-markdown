#!/usr/bin/env sh
set -eu

PYTHON_BIN="${PYTHON_BIN:-python3}"

"$PYTHON_BIN" -m pip install --no-deps --no-build-isolation -e .
"$PYTHON_BIN" -m unittest discover -s tests -v
