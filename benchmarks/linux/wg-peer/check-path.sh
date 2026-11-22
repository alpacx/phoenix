#!/bin/sh
# Run as root on the ROCK. Public server key, endpoint IPv4, UDP port.
# The socket uses Ethernet; the decrypted interface exists only in the test namespace.
set -eu
test "$#" -eq 3
test "$(tr -d '\000' </proc/device-tree/model)" = 'Radxa ROCK 4C+'
ns=phoenix-bench-check
ip netns add "$ns"
trap 'ip netns del "$ns"' EXIT
ip link add phbench-check type wireguard
if ! ip link set phbench-check netns "$ns"; then
    ip link del phbench-check
    exit 1
fi
ip netns exec "$ns" wg set phbench-check private-key /run/phoenix-bench-wg/client.key peer "$1" allowed-ips 10.77.51.1/32 endpoint "$2:$3"
ip -n "$ns" addr add 10.77.51.2/24 dev phbench-check
ip -n "$ns" link set phbench-check up
ip netns exec "$ns" ping -c 2 -W 2 10.77.51.1
ip netns exec "$ns" wg show phbench-check latest-handshakes
