#!/bin/sh
# Run cargo for platforms/linux/rust inside the static musl build container.
# Builds for the container architecture (aarch64 on Apple Silicon, like the
# targets). Never touches host networking. Usage: tools/rust-linux.sh test
set -eu
root="${PHOENIX_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
image=phoenix-rust-build:local
if ! docker image inspect "$image" >/dev/null 2>&1; then
    docker build -q -t "$image" -f "$root/platforms/linux/rust/Dockerfile.build" "$root/platforms/linux/rust" >/dev/null
fi
exec docker run --rm -v "$root":/workspace -w /workspace/platforms/linux/rust \
    -v phoenix-cargo-registry:/usr/local/cargo/registry \
    "$image" cargo "$@"
