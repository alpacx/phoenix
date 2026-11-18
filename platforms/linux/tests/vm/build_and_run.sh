#!/bin/sh
# Boot a disposable QEMU arm64 guest (systemd PID 1) built from this container
# and run check.py against the Rust `phoenix` binary and platforms/linux/deploy.
# PHOENIX_BINARY overrides the binary (default: the aarch64 release build).
set -eu
[ -f /.dockerenv ] || { echo 'Container only'; exit 1; }
binary=${PHOENIX_BINARY:-/workspace/platforms/linux/rust/target/release/phoenix}
[ -f "$binary" ] || { echo "Missing $binary: run tools/rust-linux.sh build --release"; exit 1; }
# ELF e_machine 0xb7 = AArch64: the guest cannot run an x86_64 build.
[ "$(od -An -tx1 -j18 -N2 "$binary" | tr -d ' \n')" = b700 ] || { echo "$binary is not an aarch64 ELF"; exit 1; }
work=/tmp/phoenix-vm
mkdir -p "$work/root"
tar --one-file-system --exclude=./tmp --exclude=./proc --exclude=./sys --exclude=./dev --exclude=./run --exclude=./workspace --exclude=./mnt --exclude=./.dockerenv --exclude=./etc/mtab -C / -cf "$work/root.tar" .
tar -C "$work/root" -xf "$work/root.tar"
mkdir -p "$work/root/tmp" "$work/root/proc" "$work/root/sys" "$work/root/dev" "$work/root/run" "$work/root/mnt" "$work/root/opt/source" "$work/root/opt/vm"
chmod 1777 "$work/root/tmp"
cp "$binary" "$work/root/opt/source/phoenix"
chmod 0755 "$work/root/opt/source/phoenix"
cp -R /workspace/platforms/linux/deploy "$work/root/opt/source/deploy"
cp /workspace/platforms/linux/tests/vm/check.py "$work/root/opt/vm/check.py"
ln -s /proc/self/mounts "$work/root/etc/mtab"
rm -f "$work/root/etc/machine-id"
cat > "$work/root/etc/systemd/system/phoenix-vm-test.service" <<'EOF'
[Unit]
Description=Phoenix isolated VM integration test
Requires=basic.target
After=basic.target
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /opt/vm/check.py
StandardOutput=journal+console
StandardError=journal+console
TimeoutStartSec=900
EOF
truncate -s 2G "$work/root.ext4"
mkfs.ext4 -q -F -d "$work/root" "$work/root.ext4"
kernel=$(ls /boot/vmlinuz-* | head -1)
initrd=$(ls /boot/initrd.img-* | head -1)
set +e
timeout 1200 qemu-system-aarch64 -machine virt -cpu cortex-a57 -accel tcg -m 1024 -smp 2 -nographic -nic none -kernel "$kernel" -initrd "$initrd" -append 'root=/dev/vda rw console=ttyAMA0 systemd.unit=phoenix-vm-test.service panic=1' -drive "file=$work/root.ext4,if=virtio,format=raw" > "$work/console.log" 2>&1
vm_result=$?
set -e
cat "$work/console.log"
[ "$vm_result" -eq 0 ]
grep -q 'VM ALL CHECKS PASS' "$work/console.log" || { echo 'VM checks did not finish successfully'; exit 1; }
