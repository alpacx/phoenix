#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
export IDF_PATH="${IDF_PATH:-$HOME/esp/esp-idf}"
expected=10ca0dff2f40aeb539f22d1ef88d031cf7421743
[[ "$(git -C "$IDF_PATH" rev-parse HEAD)" == "$expected" ]] || { echo 'ESP-IDF commit mismatch'; exit 1; }
export IDF_PYTHON_ENV_PATH="${IDF_PYTHON_ENV_PATH:-$HOME/.espressif/python_env/idf5.5_py3.9_env}"
export PATH="$IDF_PYTHON_ENV_PATH/bin:$PATH"
source "$IDF_PATH/export.sh" >/dev/null
idf.py "$@" build
