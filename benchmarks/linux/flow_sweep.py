"""Compare TCP concurrency on a verified macOS gateway route."""
import argparse
import json
import subprocess
from pathlib import Path
from statistics import median


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("peer")
    parser.add_argument("interface", help="Phoenix USB or Wi-Fi interface on the Mac")
    parser.add_argument("output", type=Path)
    parser.add_argument("--port", type=int, default=5201)
    parser.add_argument("--seconds", type=int, default=20)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    results = []
    for direction, flags in (("upload", []), ("download", ["-R"])):
        for repeat in range(3):
            levels = [1, 4, 8, 16, 32]
            if repeat == 1:
                levels.reverse()
            for streams in levels:
                route = subprocess.check_output(["route", "-n", "get", "-ifscope", args.interface, args.peer], text=True)
                if ["interface:", args.interface] not in [line.split() for line in route.splitlines()]:
                    raise SystemExit("Interrupted: scoped route does not use the selected interface")
                path = args.output / f"{direction}-{streams}-{repeat + 1}.json"
                with path.open("w") as out:
                    subprocess.run(["iperf3", "-4", "--bind-dev", args.interface, "-c", args.peer, "-p", str(args.port),
                                    "-P", str(streams), "-t", str(args.seconds), "-O", "2",
                                    "-J", *flags], stdout=out, check=True,
                                   timeout=args.seconds + 35)
                data = json.loads(path.read_text())
                rate = data["end"]["sum_received"]["bits_per_second"] / 1e6
                results.append((direction, streams, rate))
    summary = {}
    for direction in ("upload", "download"):
        rates = {n: median(v for d, k, v in results if d == direction and k == n)
                 for n in (1, 4, 8, 16, 32)}
        maximum = max(rates.values())
        summary[direction] = {"median_mbps": rates, "first_within_5pct":
                              min(n for n, v in rates.items() if v >= maximum * 0.95)}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
