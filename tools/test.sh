#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build-host
clang -O1 -std=c11 -Wall -Wextra -Werror -fsanitize=undefined -g -Icomponents/phoenix_core/include components/phoenix_core/firewall.c tests/test_firewall.c -o build-host/test_firewall
./build-host/test_firewall

clang -O1 -std=c11 -Wall -Wextra -Werror -fsanitize=undefined -g -Icomponents/phoenix_core/include components/phoenix_core/wg_profile.c tests/test_profile.c -o build-host/test_profile
./build-host/test_profile
