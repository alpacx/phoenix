"""ROCK-only supervisor for a bounded, reversible local benchmark session."""
import json
import os
import shutil
import ssl
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

base = Path("/run/phoenix-bench-wg")
vault = Path("/var/lib/phoenix/vpn-private.json")
signal_dir = Path(sys.argv[1])
peer = sys.argv[2]
origin = "https://127.0.0.1:8443"
tls = ssl.create_default_context(cafile="/etc/phoenix/admin-cert.pem")
token = Path("/var/lib/phoenix/admin-token").read_text().strip()


def api(path, body=None):
    req = urllib.request.Request(origin + "/api/v1/" + path,
                                 data=None if body is None else json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + token, "Origin": origin,
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, context=tls, timeout=8) as response:
        return json.load(response)


def wait_for(check, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if check():
            return
        time.sleep(2)
    raise TimeoutError("benchmark session deadline")


if Path("/proc/device-tree/model").read_bytes().rstrip(b"\0") != b"Radxa ROCK 4C+":
    raise SystemExit("unexpected board")
if not api("status").get("direct"):
    raise SystemExit("expected direct mode")
if sys.argv[3:] == ["--check"]:
    print("ready")
    sys.exit()
os.umask(0o077)
wait_for(lambda: (signal_dir / "start").exists(), 5400)
if not api("status").get("direct"):
    raise SystemExit("mode changed during direct run")
# Keep the original profile across a loss of power. Link the synced staging
# file without replacing any snapshot left by an interrupted benchmark.
backup = vault.with_name("vpn-private.pre-benchmark.json")
if backup.exists():
    raise SystemExit("previous backup present")
import tempfile
with tempfile.NamedTemporaryFile(dir=vault.parent, prefix=".bench-backup-") as stage:
    with vault.open("rb") as original:
        shutil.copyfileobj(original, stage)
    stage.flush()
    os.fsync(stage.fileno())
    os.link(stage.name, backup)
    directory = os.open(vault.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
try:
    private = (base / "client.key").read_text().strip()
    profile = (f"[Interface]\nAddress=10.77.51.2/32\nPrivateKey={private}\nDNS=10.77.51.1\n"
               f"[Peer]\nPublicKey={peer}\nEndpoint=192.168.8.124:51873\n"
               "AllowedIPs=0.0.0.0/0\nPersistentKeepalive=5\n")
    api("vpn", {"action": "wireguard", "profile": profile})
    wait_for(lambda: api("status").get("vpn_up"), 90)
    wait_for(lambda: (signal_dir / "done").exists(), 3900)
finally:
    # Reload the original private configuration into memory as well as on disk.
    subprocess.run(["systemctl", "stop", "phoenix", "phoenix-control"], check=True)
    shutil.copy2(backup, vault.with_suffix(".restore"))
    os.replace(vault.with_suffix(".restore"), vault)
    subprocess.run(["systemctl", "start", "phoenix"], check=True)
    wait_for(lambda: Path("/run/phoenix/ap/control/wlan0").exists(), 30)
    pid = subprocess.check_output(["pgrep", "-x", "hostapd"], text=True).strip()
    ctl = ["nsenter", "-t", pid, "-m", "--", "hostapd_cli", "-p", "/run/phoenix/ap/control", "-i", "wlan0"]
    for args in [["disable"], ["set","hw_mode","a"], ["set","channel","36"], ["set","ieee80211n","1"],
                 ["set","ieee80211ac","1"], ["set","ht_capab","[HT40+]"], ["set","vht_oper_chwidth","1"],
                 ["set","vht_oper_centr_freq_seg0_idx","42"], ["enable"]]:
        subprocess.run(ctl + args, check=True)
    api("vpn", {"action": "direct"})
    wait_for(lambda: api("status").get("direct"), 30)
    backup.unlink()
    print("original profile and direct mode restored", flush=True)
