#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build-host
clang -O1 -std=c11 -Wall -Wextra -Werror -fsanitize=undefined -g -Icomponents/phoenix_core/include components/phoenix_core/firewall.c tests/test_firewall.c -o build-host/test_firewall
./build-host/test_firewall

clang -O1 -std=c11 -Wall -Wextra -Werror -fsanitize=undefined -g -Icomponents/phoenix_core/include components/phoenix_core/wg_profile.c tests/test_profile.c -o build-host/test_profile
./build-host/test_profile

# Extract unchanged function bodies, so scheduler tests exercise the real vendored code.
python3 - <<'PY'
from pathlib import Path
s = Path('components_overrides/esp_tinyusb/tinyusb_net.c').read_text()
a = s[s.index('static void do_send_sync('):s.index('static void do_send_async(')]
b = s[s.index('esp_err_t tinyusb_net_send_sync('):s.index('esp_err_t tinyusb_net_init(')]
Path('build-host/usb_sync_under_test.inc').write_text(a + b)
PY
clang -O1 -std=c11 -Wall -Wextra -Werror -fsanitize=undefined -g -Ibuild-host tests/test_usb_sync.c -o build-host/test_usb_sync
./build-host/test_usb_sync

clang -O1 -std=c11 -Wall -Wextra -Werror -fsanitize=undefined -g -Icomponents/phoenix_core/include components/phoenix_core/vpn_rotation.c tests/test_vpn_rotation.c -o build-host/test_vpn_rotation
./build-host/test_vpn_rotation

clang -O1 -std=c11 -Wall -Wextra -Werror -fsanitize=undefined -g -Icomponents/phoenix_core/include components/phoenix_core/policy.c tests/test_policy.c -o build-host/test_policy
./build-host/test_policy
