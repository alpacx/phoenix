"""Run the local macOS/ROCK forwarding benchmark. No network configuration changes."""
import argparse
import csv
import json
import subprocess as sp
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEVELS = (1, 4, 8, 16, 32)
DIRECTIONS = ("upload", "download", "duplex")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("rock", "socket", "ethernet", "usb", "wifi", "output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--sweep-seconds", type=int, default=15)
    parser.add_argument("--hold-seconds", type=int, default=1800)
    parser.add_argument("--vpn-reference", type=Path,
                        help="Replay completed direct session through an active Phoenix WireGuard peer")
    args = parser.parse_args()
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    ssh = ["ssh", "-S", args.socket, "-o", "BatchMode=yes", "-o", "ConnectTimeout=4", args.rock]

    def remote(command):
        return sp.check_output(ssh + [command], timeout=12, text=True).strip()

    target = sp.check_output(["ipconfig", "getifaddr", args.ethernet], text=True).strip()
    if args.vpn_reference:
        target = "10.77.51.1"
    for dev, gateway in [(args.usb, "192.168.7.1"), (args.wifi, "192.168.9.1")]:
        route = sp.check_output(["route", "-n", "get", "-ifscope", dev, target], text=True)
        if ["gateway:", gateway] not in [s.split() for s in route.splitlines()]:
            raise RuntimeError(f"{dev}: expected Phoenix gateway {gateway}")
    context = remote("hostname; readlink /opt/phoenix; ip -br addr; ip rule; /usr/sbin/iw dev wlan0 info; cat /sys/class/net/eth0/speed")
    if "channel 36 (5180 MHz)" not in context or ("phwg0" in context) != bool(args.vpn_reference):
        raise RuntimeError("Unexpected tunnel state or Wi-Fi channel")
    (out / "context.txt").write_text(context + "\n")
    session = "suite-" + time.strftime("%Y%m%d-%H%M%S")
    remote_dir = "phoenix-bench/" + session
    remote("mkdir -m 700 " + remote_dir)
    with (HERE / "sample.py").open() as src:
        sp.run(ssh + ["cat > " + remote_dir + "/sample.py"], stdin=src, check=True)
    # A bounded lifetime also stops collection if the Mac loses management access.
    limit = args.hold_seconds + 45 * (args.sweep_seconds + 10) + 240
    pid = int(remote(f"cd {remote_dir} && (nohup python3 -u sample.py {limit} >rock.csv 2>capture.log </dev/null & echo $!)"))
    (out / "remote.txt").write_text(remote_dir + "\n")
    start = time.monotonic()
    rows = []
    rates = {}
    def elapsed():
        return round(time.monotonic() - start, 2)

    def phase(label, devices, direction, streams, seconds):
        begin = elapsed()
        def run(item):
            i, dev = item
            directory = out / f"{label}-{dev}"
            cmd = ["bash", str(HERE / "mac_lan_probe.sh"), args.ethernet, dev, direction,
                   str(seconds), str(streams), str(25192 + i), str(directory)]
            if args.vpn_reference:
                directory.mkdir()
                cmd = ["iperf3", "-4", "--bind-dev", dev, "-c", target, "-p", str(25192+i),
                       "-P", str(streams), "-t", str(seconds), "--connect-timeout", "3000", "-J"]
                cmd += {"upload": [], "download": ["-R"], "duplex": ["--bidir"]}[direction]
            with (out / f"{label}-{dev}-latency.txt").open("w") as log:
                ping = sp.Popen(["ping", "-b", dev, "-i", "1", target], stdout=log, stderr=log)
                try:
                    if args.vpn_reference:
                        with (directory / "client.json").open("w") as result_file:
                            sp.run(cmd, stdout=result_file, check=True, timeout=seconds + 35)
                    else:
                        sp.run(cmd, check=True, timeout=seconds + 35)
                finally:
                    ping.terminate()
                    ping.wait(timeout=5)
            data = json.loads((directory / "client.json").read_text())
            if data.get("error"):
                raise RuntimeError(data["error"])
            end = data["end"]
            primary = end["sum_received"]["bits_per_second"] / 1e6
            reverse = end.get("sum_received_bidir_reverse", {}).get("bits_per_second", 0) / 1e6
            return dict(device=dev, upload=0 if direction == "download" else primary,
                        download=primary if direction == "download" else reverse)
        with ThreadPoolExecutor(len(devices)) as pool:
            results = list(pool.map(run, enumerate(devices)))
        for result in results:
            rows.append(dict(phase=label, direction=direction, streams_per_direction=streams,
                             start_s=begin, end_s=elapsed(), **result))
        with (out / "phases.csv").open("w") as file:
            writer = csv.DictWriter(file, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        print(label, results, flush=True)
        return sum(r["upload"] + r["download"] for r in results)

    try:
        time.sleep(30)
        if args.vpn_reference:
            with (args.vpn_reference / "phases.csv").open() as reference:
                plan = list(csv.DictReader(reference))
            if not any(row["phase"] == "sustained" for row in plan):
                raise ValueError("Direct session lacks its sustained phase")
            for label in dict.fromkeys(row["phase"] for row in plan):
                group = [row for row in plan if row["phase"] == label]
                phase(label, [row["device"] for row in group], group[0]["direction"],
                      int(group[0]["streams_per_direction"]),
                      args.hold_seconds if label == "sustained" else args.sweep_seconds)
        else:
            for dev in (args.usb, args.wifi):
                for n in LEVELS:
                    rates[dev, n] = sum(phase(f"sweep-{n}-{dev}-{d}", [dev], d, n, args.sweep_seconds) for d in DIRECTIONS[:2])
            # Same total flow budget for single-interface and mixed trials.
            best = max(2, max(next(n for n in LEVELS if rates[dev, n] >= 0.95 * max(rates[dev, m] for m in LEVELS))
                              for dev in (args.usb, args.wifi)))
            choices = []
            for devices in ([args.usb], [args.wifi], [args.usb, args.wifi]):
                n = best // len(devices)
                label = "-".join(devices)
                for direction in DIRECTIONS:
                    phase(f"compare-{label}-{direction}", devices, direction, n, args.sweep_seconds)
                    # Select sustained phase using average measured CPU during this trial.
                    first, last = rows[-1]["start_s"], rows[-1]["end_s"]
                    cpu = float(remote(f"""awk -F, 'NR==1 {{for(i=1;i<=NF;i++) if($i=="cpu") c=i}}
                        NR>1 && $2>={first+2} && $2<={last} {{s+=$c;n++}} END {{if(n) print s/n; else exit 1}}' {remote_dir}/rock.csv"""))
                    choices.append((cpu, devices, direction, n))
            _, devices, direction, n = max(choices, key=lambda v: v[0])
            phase("sustained", devices, direction, n, args.hold_seconds)
        time.sleep(60)
    finally:
        remote(f'if [ "$(readlink /proc/{pid}/cwd)" = "$HOME/{remote_dir}" ]; then kill {pid}; fi')
        with (out / "rock.csv").open("w") as file:
            sp.run(ssh + ["cat " + remote_dir + "/rock.csv"], stdout=file, check=True)
    sp.run(["python3", str(HERE / "report.py"), str(out), str(out / "report"),
            "--context", ("VPN WireGuard locale. " if args.vpn_reference else "Forwarding diretto. ") + "Concorrenza e throughput per fase in phases.csv. Riposo, scalini, confronto e carico sostenuto."], check=True)
    print("complete", flush=True)


if __name__ == "__main__":
    main()
