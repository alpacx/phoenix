#!/bin/sh
# Linux services (Rust): unit tests + frozen parity fixtures, in the Docker
# build container. Container-only kernel/packet tests are separate (see
# docs/PROJECT_STRUCTURE.md).
set -eu
cd "$(dirname "$0")/.."
exec tools/rust-linux.sh test "$@"
