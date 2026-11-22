#!/bin/sh
# Temporary, isolated endpoint. Only the public key is printed.
set -eu
umask 077
wg genkey > /run/peer.key
ip link add benchwg type wireguard
wg set benchwg private-key /run/peer.key listen-port 51873
ip addr add 10.77.51.1/24 dev benchwg
ip link set benchwg up
wg show benchwg public-key
iperf3 -s -B 10.77.51.1 -p 25192 &
exec iperf3 -s -B 10.77.51.1 -p 25193
