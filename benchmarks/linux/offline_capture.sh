#!/bin/sh
# Run on the ROCK as the lab user, alongside sample.py.
set -eu
duration=${1:?duration in seconds}
output=${2:?new output directory}
case "$duration" in ''|*[!0-9]*) exit 2;; esac
test "$duration" -gt 0
source_dir=$(dirname "$0")
test -r "$source_dir/sample.py"
umask 077
mkdir "$output"
nohup sh -c '
    python3 -u "$1" "$2" > "$3/rock.csv"
    status=$?
    printf "%s\n" "$status" > "$3/exit-code"
    exit "$status"
' sh "$source_dir/sample.py" "$duration" "$output" </dev/null >"$output/capture.log" 2>&1 &
echo "$!" >"$output/pid"
