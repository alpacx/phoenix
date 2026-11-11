#!/bin/sh
set -eu
[ -f /.dockerenv ] || { echo 'Container only'; exit 1; }
work=/tmp/phoenix-vm
mkdir -p "$work/root"
tar --one-file-system --exclude=./tmp --exclude=./proc --exclude=./sys --exclude=./dev --exclude=./run --exclude=./workspace --exclude=./.dockerenv --exclude=./etc/mtab -C / -cf "$work/root.tar" .
tar -C "$work/root" -xf "$work/root.tar"
mkdir -p "$work/root/tmp" "$work/root/proc" "$work/root/sys" "$work/root/dev" "$work/root/run" "$work/root/opt/source/platforms/linux" "$work/root/opt/source/shared" "$work/root/opt/vm"
chmod 1777 "$work/root/tmp"
cp -R /workspace/platforms/linux/service /workspace/platforms/linux/deploy "$work/root/opt/source/platforms/linux/"
cp -R /workspace/shared/web "$work/root/opt/source/shared/"
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
TimeoutStartSec=600
EOF
truncate -s 2G "$work/root.ext4"
mkfs.ext4 -q -F -d "$work/root" "$work/root.ext4"
kernel=$(ls /boot/vmlinuz-* | head -1)
initrd=$(ls /boot/initrd.img-* | head -1)
set +e
timeout 600 qemu-system-aarch64 -machine virt -cpu cortex-a57 -accel tcg -m 1024 -smp 2 -nographic -nic none -kernel "$kernel" -initrd "$initrd" -append 'root=/dev/vda rw console=ttyAMA0 systemd.unit=phoenix-vm-test.service panic=1' -drive "file=$work/root.ext4,if=virtio,format=raw" > "$work/console.log" 2>&1
vm_result=$?
set -e
cat "$work/console.log"
[ "$vm_result" -eq 0 ]
python3 -c "from pathlib import Path; assert 'VM ALL CHECKS PASS' in Path('/tmp/phoenix-vm/console.log').read_text(), 'VM checks did not finish successfully'"
