#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/platforms/linux/service${PYTHONPATH:+:$PYTHONPATH}"
python3 -m unittest discover -s platforms/linux/tests -v
