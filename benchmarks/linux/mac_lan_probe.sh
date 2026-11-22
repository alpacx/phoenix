#!/bin/bash
# Usage: bash mac_lan_probe.sh SERVER_IF CLIENT_IF DIRECTION SECONDS STREAMS PORT OUTDIR
set -eu
[[ $# == 7 ]] || exit 2
server_if=$1; client_if=$2; direction=$3; seconds=$4; streams=$5; port=$6; out=$7
[[ "$server_if" != "$client_if" ]] || exit 2
flags=(-J)
case "$direction" in upload) ;; download) flags+=(-R);; duplex) flags+=(--bidir);; *) exit 2;; esac
addr=$(ipconfig getifaddr "$server_if")
route_info=$(route -n get -ifscope "$client_if" "$addr")
[[ $(awk '/interface:/{print $2}' <<< "$route_info") == "$client_if" ]] || exit 1
mkdir "$out"
printf '%s\n' "$route_info" > "$out/route.txt"
iperf3 -4 -s -1 -B "$addr%$server_if" -p "$port" -J > "$out/server.json" &
server=$!
trap 'kill "$server" 2>/dev/null || true' EXIT
sleep 1
kill -0 "$server"
iperf3 -4 -c "$addr" --bind-dev "$client_if" -p "$port" -t "$seconds" -P "$streams" \
  --connect-timeout 3000 "${flags[@]}" > "$out/client.json"
wait "$server"
trap - EXIT
