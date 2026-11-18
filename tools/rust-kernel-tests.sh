#!/bin/sh
# Container-only checks of the Rust services against real Linux tools:
# the #[ignore] `kernel_*` tests (nft, ip, wg, conntrack, dnsmasq + busybox
# udhcpc, NetworkManager, bound TLS/DoH in a network namespace) and
# `systemd-analyze verify` of the deploy units.
#
# Everything runs in a disposable phoenix-linux-test:local container. The
# capabilities (NET_ADMIN, SYS_ADMIN for `ip netns`) apply only inside its own
# namespaces: never the host network, never a target.
#   tools/rust-kernel-tests.sh
set -eu
root="${PHOENIX_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
image=phoenix-linux-test:local

executable=$("$root/tools/rust-linux.sh" test --lib --no-run --message-format=json \
    | grep -o '"executable":"[^"]*/phoenix_linux-[0-9a-f]*"' | tail -1 | cut -d'"' -f4)
[ -n "$executable" ] || { echo "Rust test executable not found" >&2; exit 1; }
"$root/tools/rust-linux.sh" build --release
if ! docker image inspect "$image" >/dev/null 2>&1; then
    docker build -q -t "$image" -f "$root/platforms/linux/tests/integration/Dockerfile" "$root/platforms/linux/tests/integration"
fi

docker run --rm --init --cap-add NET_ADMIN --cap-add SYS_ADMIN --security-opt apparmor=unconfined \
    --sysctl net.ipv4.conf.all.rp_filter=0 --sysctl net.ipv4.conf.default.rp_filter=0 \
    --mount type=bind,source="$root",target=/workspace,readonly -w /workspace \
    "$image" sh -ec '
"$1" --ignored --test-threads=1 kernel_
useradd --system --no-create-home --shell /usr/sbin/nologin phoenix-web
for dir in /opt/phoenix/bin /opt/phoenix-bootstrap/bin; do
    install -D -m 0755 platforms/linux/rust/target/release/phoenix "$dir/phoenix"
done
systemd-analyze verify platforms/linux/deploy/*.service platforms/linux/deploy/*.socket
echo "systemd-analyze verify: $(ls platforms/linux/deploy/*.service platforms/linux/deploy/*.socket | wc -l) units PASS"
echo "RUST KERNEL TESTS PASS (USB enumeration, radio/AP and VPN provider are hardware/remote tests)"
' kernel-tests "$executable"
