"""Systemd stop/crash guard for the dedicated Phoenix Linux target."""
from pathlib import Path
from .runtime import Runner


def block(runner, forwarding=Path('/proc/sys/net/ipv4/ip_forward')):
    # Disable forwarding even if nft userspace is unavailable or the table is damaged.
    forwarding.write_text('0')
    exists = runner(['nft', 'list', 'table', 'inet', 'phoenix_stop'], optional=True).returncode == 0
    script = ('delete table inet phoenix_stop\n' if exists else '') + '''table inet phoenix_stop {
 chain forward {
  type filter hook forward priority -20; policy drop;
  counter drop
 }
}
'''
    runner(['nft', '-f', '-'], data=script)


if __name__ == '__main__':
    block(Runner())
