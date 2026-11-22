"""Plot a continuous telemetry capture and one iperf3 TCP load phase."""
import argparse
import csv
import json
from pathlib import Path
from statistics import mean

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path)
    parser.add_argument("--idle-seconds", type=float, required=True,
                        help="Seconds from start of sampling to start of load")
    args = parser.parse_args()
    raw = args.session / "raw"
    with (raw / "rock.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    load = json.loads((raw / "load.json").read_text())
    intervals = [i["sum"] for i in load["intervals"] if not i["sum"].get("omitted")]
    if not rows or not intervals or load.get("error"):
        parser.error("Incomplete capture")
    start = args.idle_seconds
    end = start + intervals[-1]["end"]
    t = [float(row["elapsed_s"]) for row in rows]
    temperatures = [key for key in rows[0] if key.startswith("temp_")]
    fig, axes = plt.subplots(4, 1, figsize=(11, 9), sharex=True, layout="constrained")
    axes[0].stairs([i["bits_per_second"] / 1e6 for i in intervals],
                   [start + i["start"] for i in intervals] + [end], baseline=None)
    axes[0].set_ylabel("TCP inviato\n(Mbit/s)")
    for key in temperatures:
        axes[1].plot(t, [float(r[key]) for r in rows], label=key[5:-2])
    axes[1].legend()
    axes[1].set_ylabel("Temperatura (°C)")
    axes[2].plot(t, [float(r["cpu"]) for r in rows], label="Media CPU")
    cores = [key for key in rows[0] if key.startswith("cpu") and key[3:].isdigit()]
    axes[2].plot(t, [max(float(r[k]) for k in cores if r[k]) for r in rows],
                 alpha=0.65, label="Core più occupato")
    axes[2].legend()
    axes[2].set_ylabel("Utilizzo (%)")
    axes[3].plot(t, [float(r["available_MiB"]) for r in rows])
    axes[3].set_ylabel("RAM disponibile\n(MiB)")
    axes[3].set_xlabel("Secondi dall’avvio del campionamento")
    for ax in axes:
        ax.axvspan(start, end, color="orange", alpha=0.1)
        ax.grid(axis="y", alpha=0.2)
    fig.suptitle("ROCK 4C+ · riposo, ricezione TCP, recupero")
    fig.savefig(args.session / "profilo.png", dpi=150)
    plt.close(fig)
    report = ["# Profilo temporale ROCK 4C+", "",
              "Mac su Wi-Fi del router → Ethernet ROCK. iperf3 termina sulla ROCK. "
              "Campionamento ogni secondo. L’allineamento delle fasi è approssimato al secondo.",
              "", "![Profilo](profilo.png)", "",
              "| Fase | Campioni | CPU media | RAM disponibile minima | " +
              " | ".join(key[5:-2] + " media / picco °C" for key in temperatures) + " |",
              "|" + "---|" * (4 + len(temperatures))]
    for label, begin, stop in (("Riposo", 0, start), ("Carico", start, end),
                               ("Recupero", end, t[-1]+1)):
        block = [row for row, ts in zip(rows, t) if begin <= ts < stop]
        if not block:
            continue
        cells = [label, str(len(block)), f'{mean(float(r["cpu"]) for r in block):.1f}%',
                 f'{min(float(r["available_MiB"]) for r in block):.1f} MiB']
        for key in temperatures:
            values = [float(r[key]) for r in block]
            cells.append(f"{mean(values):.1f} / {max(values):.1f}")
        report.append("| " + " | ".join(cells) + " |")
    report += ["", "Throughput TCP ricevuto medio: "
               f'{load["end"]["sum_received"]["bits_per_second"]/1e6:.1f} Mbit/s.', "",
               "| Finestra sotto carico | Mbit/s inviati |", "|---|---:|"]
    for offset in range(0, len(intervals), 30):
        chunk = intervals[offset:offset+30]
        rate = sum(i["bytes"] for i in chunk)*8/1e6/sum(i["seconds"] for i in chunk)
        report.append(f'| {chunk[0]["start"]:.0f}–{chunk[-1]["end"]:.0f} s | {rate:.1f} |')
    (args.session / "debrief.md").write_text("\n".join(report) + "\n")


if __name__ == "__main__":
    main()
