#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
json_source="${IDF_PATH:-$HOME/esp/esp-idf}/components/json/cJSON"
mkdir -p build-host
clang -std=c11 -O1 -Wall -Wextra -Werror -fsanitize=undefined -Itests/history_stubs -I"$json_source" tests/test_vpn_history.c "$json_source/cJSON.c" -o build-host/test_vpn_history
./build-host/test_vpn_history
