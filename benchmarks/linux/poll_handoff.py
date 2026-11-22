"""Poll one direct suite every ten minutes and run its VPN replay once."""
import datetime
import subprocess as sp
import sys
import time
from pathlib import Path

direct, output, socket, rock, remote_dir = sys.argv[1:]
direct, output = Path(direct), Path(output)
ssh = ["ssh", "-S", socket, "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", rock]
log = Path(str(direct) + ".log")
errors = Path(str(direct) + ".errors")


def status(msg):
    print(datetime.datetime.now().astimezone().isoformat(timespec="seconds"), msg, flush=True)


for _ in range(12):
    # Keep the authenticated local control connection usable between phases.
    sp.run(ssh + ["true"], check=True, timeout=15)
    lines = log.read_text().splitlines()
    if lines and lines[-1] == "complete":
        break
    if errors.exists() and "Traceback (most recent call last)" in errors.read_text():
        raise SystemExit("direct run failed; VPN left inactive")
    status("direct in progress; next check in 10 minutes")
    time.sleep(600)
else:
    raise SystemExit("direct run did not finish before deadline")

status("direct complete; starting VPN validation")
try:
    sp.run(ssh + ["touch " + remote_dir + "/start"], check=True)
    for _ in range(45):
        if sp.run(ssh + ["ip -4 addr show phwg0 | grep -q 10.77.51.2"], stderr=sp.DEVNULL).returncode == 0:
            break
        time.sleep(2)
    else:
        raise RuntimeError("Phoenix WireGuard interface unavailable")
    for dev in ("en14", "en0"):
        sp.run(["iperf3", "-4", "--bind-dev", dev, "-c", "10.77.51.1", "-p", "25192",
                "-t", "1", "--connect-timeout", "5000"], check=True, timeout=15)
    status("USB and Wi-Fi VPN validated; replay running")
    result = sp.Popen([sys.executable, "-u", str(Path(__file__).with_name("direct_suite.py")),
                       "--rock", rock, "--socket", socket, "--ethernet", "en8", "--usb", "en14",
                       "--wifi", "en0", "--output", str(output), "--vpn-reference", str(direct)])
    while True:
        try:
            if result.wait(timeout=600) != 0:
                raise RuntimeError("VPN replay failed")
            break
        except sp.TimeoutExpired:
            status("VPN replay in progress")
    status("VPN replay complete")
finally:
    sp.run(ssh + ["touch " + remote_dir + "/done"], check=True)
