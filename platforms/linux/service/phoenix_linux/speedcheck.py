"""Native HTTPS download benchmark; no automatic interface or server fallback."""
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
from .firewall import interface

ENDPOINT = 'https://speedtest3.serverius.net/files/1000mb.bin'
STREAMS = 4
DURATION = 10


def available():
    return shutil.which('curl') is not None


def temperatures():
    values = []
    for path in Path('/sys/class/thermal').glob('thermal_zone*/temp'):
        try:
            values.append(int(path.read_text()) / 1000)
        except (ValueError, OSError):
            pass
    return values


def sanitize(samples, elapsed):
    if not math.isfinite(elapsed) or elapsed <= 0 or len(samples) != STREAMS:
        raise ValueError('invalid_measurement')
    total = 0
    for code, output in samples:
        size, seconds, http = output.split()
        size, seconds = float(size), float(seconds)
        if (code not in (0, 28) or http != '200' or not math.isfinite(size)
                or not math.isfinite(seconds) or size <= 0 or seconds <= 0
                or (code == 28 and seconds < DURATION - .5)):
            raise ValueError('invalid_measurement')
        total += size
    return {'download_mbps': round(total * 8 / elapsed / 1e6, 2),
            'download_mb': round(total / 1e6, 1), 'upload_mbps': None, 'ping_ms': None,
            'streams': STREAMS, 'engine': 'curl-native', 'metric': 'https_download',
            'server': 'Serverius DC3 · HTTPS', 'server_id': 'serverius-dc3',
            'measurement_seconds': round(elapsed, 2)}


class Measurement:
    def __init__(self):
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.started = None
        self.value = {'state': 'idle'}

    def status(self):
        with self.lock:
            value = dict(self.value)
            if value['state'] == 'running':
                value['elapsed_seconds'] = int(time.monotonic() - self.started)
            return value

    def prepare(self, mode, name, destination):
        interface(name)
        with self.lock:
            if self.started is not None and time.monotonic() - self.started < 60:
                raise ValueError('speedtest_cooldown')
            self.stop.clear()
            self.started = time.monotonic()
            self.value = {'state': 'running', 'mode': mode, 'destination': destination,
                          'server': 'Serverius DC3 · HTTPS', 'engine': 'curl-native',
                          'started_at': int(time.time()), 'elapsed_seconds': 0}

    def cancel(self):
        self.stop.set()

    def run(self, name):
        error, result, peak = '', {}, None
        processes, outputs = [], []
        try:
            name = interface(name)
            if not Path('/sys/class/net', name).exists():
                raise ValueError('missing_interface')
            curl = shutil.which('curl')
            if not curl:
                raise ValueError('curl_missing')
            temps = temperatures()
            peak = max(temps) if temps else None
            if peak is not None and peak >= 75:
                error = 'temperature_limit'
            elif self.stop.is_set():
                error = 'cancelled'
            else:
                start = time.monotonic()
                for _ in range(STREAMS):
                    output = tempfile.TemporaryFile()
                    outputs.append(output)
                    # --disable first: ignore .curlrc. No proxy, redirect or retry.
                    processes.append(subprocess.Popen([
                        curl, '--disable', '-4', '--interface', 'if!' + name,
                        '--noproxy', '*', '--proto', '=https', '--connect-timeout', '5',
                        '--max-time', str(DURATION), '--silent', '--output', '/dev/null',
                        '--write-out', '%{size_download} %{time_total} %{http_code}', ENDPOINT],
                        stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.DEVNULL,
                        close_fds=True))
                while any(p.poll() is None for p in processes):
                    temps = temperatures()
                    if temps:
                        peak = max(([peak] if peak is not None else []) + temps)
                    if self.stop.is_set():
                        error = 'cancelled'
                    elif peak is not None and peak >= 75:
                        error = 'temperature_limit'
                    elif time.monotonic() - self.started >= 20:
                        error = 'time_limit'
                    if error:
                        break
                    self.stop.wait(.1)
                if not error:
                    elapsed = time.monotonic() - start
                    samples = []
                    for process, output in zip(processes, outputs):
                        output.seek(0)
                        samples.append((process.returncode, output.read(1024).decode('ascii')))
                    result = sanitize(samples, elapsed)
        except Exception:
            error = 'measurement_failed'
        finally:
            # Every child is stopped, including partial startup and cancellation.
            for process in processes:
                if process.poll() is None:
                    process.terminate()
            for process in processes:
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1)
            for output in outputs:
                output.close()
            with self.lock:
                self.value.update(result, state='cancelled' if error == 'cancelled' else 'error' if error else 'complete',
                                  error=error, peak_c=round(peak, 1) if peak is not None else None,
                                  elapsed_seconds=int(time.monotonic() - self.started))
