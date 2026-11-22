"""Read-only Linux sampler. Write one CSV per benchmark phase on stdout."""
import argparse
import csv
import sys
import time
from pathlib import Path


def cpu_ticks():
    rows = {}
    for line in Path('/proc/stat').read_text().splitlines():
        label, *values = line.split()
        if label.startswith('cpu'):
            v = list(map(int, values[:8]))
            rows[label] = (sum(v), v[3] + v[4], v[6])
    return rows


def read_number(path, scale):
    try:
        return round(int(path.read_text()) / scale, 2)
    except (ValueError, OSError):
        return ''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('seconds', type=int)
    args = parser.parse_args()
    if args.seconds < 1:
        parser.error('duration must be positive')
    sensors = {}
    for zone in sorted(Path('/sys/class/thermal').glob('thermal_zone*')):
        name = zone.joinpath('type').read_text().strip()
        sensors[f'temp_{zone.name}_{name}_C'] = (zone / 'temp', 1000)
    for policy in sorted(Path('/sys/devices/system/cpu/cpufreq').glob('policy*')):
        sensors[f'freq_{policy.name}_MHz'] = (policy / 'scaling_cur_freq', 1000)
    previous = cpu_ticks()
    names = list(previous)
    fields = ['unix_s', 'elapsed_s', 'available_MiB', 'swap_used_MiB', 'softirq_pct']
    writer = csv.DictWriter(sys.stdout, fieldnames=fields + names + list(sensors))
    writer.writeheader()
    start = time.monotonic()
    for second in range(1, args.seconds + 1):
        time.sleep(max(0, start + second - time.monotonic()))
        current = cpu_ticks()
        mem = {p[0].rstrip(':'): int(p[1]) for p in
               (line.split() for line in Path('/proc/meminfo').read_text().splitlines())}
        row = dict(unix_s=round(time.time(), 3), elapsed_s=round(time.monotonic()-start, 3),
                   available_MiB=round(mem['MemAvailable']/1024, 1),
                   swap_used_MiB=round((mem['SwapTotal']-mem['SwapFree'])/1024, 1))
        for name in names:
            if name in current and name in previous:
                total, idle, soft = (a-b for a,b in zip(current[name], previous[name]))
                if total > 0:
                    row[name] = round(100*(total-idle)/total, 1)
                    if name == 'cpu':
                        row['softirq_pct'] = round(100*soft/total, 1)
        row.update({k: read_number(*v) for k,v in sensors.items()})
        writer.writerow(row)
        sys.stdout.flush()
        previous = current


if __name__ == '__main__':
    main()
