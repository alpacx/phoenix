"""Generate a debrief from client-side TCP iperf3 JSON and optional sample.py CSV."""
import argparse
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--context', required=True, help='Build, topology, cooling and limits')
    args = parser.parse_args()
    runs = []
    notes = ['# Debrief Phoenix', '', args.context, '']
    telemetry = []
    for path in sorted(args.source.glob('*.json')):
        data = json.loads(path.read_text())
        if 'error' in data:
            notes.append(f'- {path.name}: prova fallita.')
            continue
        test = data.get('start', {}).get('test_start', {})
        if test.get('protocol') != 'TCP':
            continue
        reverse = bool(test.get('reverse'))
        directions = [('sum_received', 'verso client' if reverse else 'dal client')]
        if test.get('bidir'):
            directions = [('sum_received', 'dal client'), ('sum_received_bidir_reverse', 'verso client')]
        for key, direction in directions:
            summary = data['end'][key]
            runs.append((path.stem, direction, test['num_streams'], summary['seconds'],
                         summary['bits_per_second']/1e6))
    for path in sorted(args.source.glob('*.csv')):
        with path.open() as stream:
            rows = list(csv.DictReader(stream))
        if rows and 'available_MiB' in rows[0]:
            telemetry.append((path.stem, rows))
    phases_path = args.source / "phases.csv"
    if phases_path.exists():
        with phases_path.open() as stream:
            phases = list(csv.DictReader(stream))
        args.output.mkdir(parents=True, exist_ok=True)
        fig, axes = plt.subplots(2, 1, sharex=True, figsize=(12, 7), layout="constrained")
        for dev in sorted({p["device"] for p in phases}):
            for ax, direction in zip(axes, ("upload", "download")):
                legend = dev
                for phase in (p for p in phases if p["device"] == dev and float(p[direction]) > 0):
                    base = args.source / (phase["phase"] + "-" + dev)
                    data = json.loads((base / "client.json").read_text())
                    reverse = direction == "download" and phase["direction"] == "duplex"
                    key = "sum_bidir_reverse" if reverse else "sum"
                    intervals = [part[key] for part in data["intervals"] if key in part]
                    if intervals:
                        origin = float(phase["end_s"]) - intervals[-1]["end"]
                        ax.plot([(origin + v["end"])/60 for v in intervals],
                                [v["bits_per_second"]/1e6 for v in intervals],
                                color="tab:blue" if dev == sorted({p["device"] for p in phases})[0] else "tab:orange",
                                label=legend)
                        legend = "_nolegend_"
                ax.set_ylabel(direction + " (Mbit/s)")
        for ax in axes:
            ax.legend()
            ax.grid(alpha=.2)
        axes[-1].set_xlabel("Minuti da inizio sessione")
        fig.savefig(args.output / "throughput-temporale.png", dpi=150)
        plt.close(fig)
        notes += ["", "![Throughput nel tempo](throughput-temporale.png)", "",
                  "| Fase | Interfaccia | Flussi per direzione | Upload ricevuto | Download ricevuto |",
                  "|---|---|---:|---:|---:|"]
        for phase in phases:
            notes.append("| {phase} | {device} | {streams_per_direction} | {up:.1f} Mbit/s | {down:.1f} Mbit/s |".format(
                **phase, up=float(phase["upload"]), down=float(phase["download"])))
    if not runs and not telemetry:
        parser.error('Nessuna misura valida nella cartella')
    args.output.mkdir(parents=True, exist_ok=True)
    if runs:
        fig, ax = plt.subplots(figsize=(9, max(3, len(runs)*0.48+1)))
        labels = [f'{n} · {d}' for n,d,*_ in runs]
        bars = ax.barh(range(len(runs)), [r[-1] for r in runs])
        ax.set_yticks(range(len(runs)), labels=labels)
        ax.bar_label(bars, fmt='%.1f', padding=3)
        ax.margins(x=.13)
        ax.set_xlabel('Throughput TCP ricevuto (Mbit/s)')
        fig.tight_layout()
        fig.savefig(args.output/'throughput.png', dpi=150)
        plt.close(fig)
        notes += ['![Throughput](throughput.png)', '', '| Prova | Direzione | Flussi | s | Mbit/s ricevuti |',
                  '|---|---|---:|---:|---:|']
        notes += [f'| {n} | {d} | {s} | {t:.1f} | {b:.1f} |' for n,d,s,t,b in runs]
    for name, rows in telemetry:
        x = [float(r['elapsed_s']) for r in rows]
        groups = [('Utilizzo (%)', [k for k in rows[0] if k.startswith('cpu') or k=='softirq_pct']),
                  ('Memoria (MiB)', ['available_MiB','swap_used_MiB']),
                  ('Temperatura (°C)', [k for k in rows[0] if k.startswith('temp_')]),
                  ('Frequenza (MHz)', [k for k in rows[0] if k.startswith('freq_')])]
        fig, axes = plt.subplots(4, figsize=(11,10),sharex=True)
        notes += ['', f'## {name}', '', f'Memoria disponibile minima: {min(float(r["available_MiB"]) for r in rows):.1f} MiB.']
        for ax,(label,keys) in zip(axes, groups):
            for k in keys:
                values = [float(r[k]) if r[k] else float('nan') for r in rows]
                ax.plot(x,values,label=k)
                valid = [v for v in values if v==v]
                if valid and k.startswith('temp_'):
                    notes.append(f'- {k}: picco {max(valid):.1f} °C, ultimo campione {valid[-1]:.1f} °C.')
            ax.set_ylabel(label)
            if keys:
                ax.legend(fontsize=7,ncol=3)
        axes[-1].set_xlabel('Secondi da inizio fase')
        fig.tight_layout()
        fig.savefig(args.output/f'{name}-telemetria.png',dpi=140)
        plt.close(fig)
        notes += ['', f'![Telemetria]({name}-telemetria.png)']
    if not telemetry:
        notes += ['', 'Telemetria della scheda assente. Questi dati non permettono di dimensionare RAM, CPU o dissipazione.']
    (args.output/'debrief.md').write_text('\n'.join(notes)+'\n')


if __name__ == '__main__':
    main()
