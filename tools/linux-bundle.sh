#!/bin/sh
# Build the static release binary and a format-2 application bundle in the
# musl build container; optionally sign it as a release for the updater.
#   tools/linux-bundle.sh OUTPUT.zip
#   tools/linux-bundle.sh OUTPUT.phx --sign KEY.pem --version V --sequence N
# The signing key is mounted read-only into the container and never copied.
set -eu
usage() { echo "usage: tools/linux-bundle.sh OUTPUT [--sign KEY.pem --version V --sequence N]" >&2; exit 2; }
[ $# -ge 1 ] || usage
output=$1; shift
key=; version=; sequence=
while [ $# -gt 0 ]; do
    case $1 in
        --sign) [ $# -ge 2 ] || usage; key=$2; shift 2 ;;
        --version) [ $# -ge 2 ] || usage; version=$2; shift 2 ;;
        --sequence) [ $# -ge 2 ] || usage; sequence=$2; shift 2 ;;
        *) usage ;;
    esac
done
if [ -n "$key" ] && { [ -z "$version" ] || [ -z "$sequence" ]; }; then usage; fi
if [ -z "$key" ] && { [ -n "$version" ] || [ -n "$sequence" ]; }; then usage; fi
[ ! -e "$output" ] || { echo "Refusing to overwrite $output" >&2; exit 1; }

root="${PHOENIX_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
image=phoenix-rust-build:local
"$root/tools/rust-linux.sh" build --release
binary=platforms/linux/rust/target/release/phoenix
echo "Release binary: $(wc -c < "$root/$binary" | tr -d ' ') bytes"

out_dir=$(cd "$(dirname "$output")" && pwd)
name=$(basename "$output")
payload=$name
[ -z "$key" ] || payload=".$name.payload.zip"
[ ! -e "$out_dir/$payload" ] || { echo "Refusing to overwrite $out_dir/$payload" >&2; exit 1; }
run() { docker run --rm -v "$root":/workspace:ro -v "$out_dir":/out "$@"; }
run "$image" "/workspace/$binary" package build "/out/$payload" \
    --binary "/workspace/$binary" --deploy-dir /workspace/platforms/linux/deploy
if [ -n "$key" ]; then
    key_dir=$(cd "$(dirname "$key")" && pwd)
    status=0
    run -v "$key_dir/$(basename "$key")":/key.pem:ro "$image" "/workspace/$binary" update sign \
        --payload "/out/$payload" --output "/out/$name" --key /key.pem \
        --version "$version" --sequence "$sequence" || status=$?
    rm -f "$out_dir/$payload"
    [ "$status" -eq 0 ] || exit "$status"
fi
echo "Created $out_dir/$name"
