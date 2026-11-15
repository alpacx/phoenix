"""Bound HTTPS upload of synthetic sparse payloads; count acknowledged requests."""
import math
import subprocess
import tempfile
import threading
import time

ENDPOINT = 'https://speed.cloudflare.com/__up'


def acknowledged(code, output, expected):
    size, status = output.split()
    size = float(size)
    if code != 0 or status != '200' or not math.isfinite(size) or size != expected:
        raise ValueError('upload_not_acknowledged')
    return int(size)


def run(curl, name, stop, temperature, duration=10, streams=4):
    start = time.monotonic()
    deadline = start + duration
    abort = threading.Event()
    counts = [0] * streams
    failures = []
    peak = None

    def transfer(index):
        process = None
        try:
            # Sparse zero-filled file: bounded size, no user data or bulk disk writes.
            with tempfile.NamedTemporaryFile(prefix='phoenix-upload-') as payload:
                size = 256 * 1024
                while not abort.is_set() and not stop.is_set() and time.monotonic() < deadline:
                    payload.truncate(size)
                    payload.flush()
                    remaining = deadline - time.monotonic()
                    if remaining <= .05:
                        break
                    sent_at = time.monotonic()
                    process = subprocess.Popen([
                        curl, '--disable', '-4', '--interface', 'if!' + name,
                        '--noproxy', '*', '--proto', '=https', '--connect-timeout', '5',
                        '--max-time', str(remaining), '--silent', '--output', '/dev/null',
                        '--request', 'POST', '--header', 'Content-Type: application/octet-stream',
                        '--header', 'Expect:', '--upload-file', payload.name,
                        '--write-out', '%{size_upload} %{http_code}', ENDPOINT],
                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                    while True:
                        try:
                            output, _ = process.communicate(timeout=.1)
                            break
                        except subprocess.TimeoutExpired:
                            if abort.is_set() or stop.is_set() or time.monotonic() >= deadline:
                                process.terminate()
                                try:
                                    output, _ = process.communicate(timeout=1)
                                except subprocess.TimeoutExpired:
                                    process.kill(); output, _ = process.communicate()
                                break
                    if process.returncode == 0:
                        counts[index] += acknowledged(0, output.decode('ascii'), size)
                        elapsed = max(.001, time.monotonic() - sent_at)
                        size = min(16 * 1024 * 1024, max(16 * 1024, int(size / elapsed * .5)))
                    elif (time.monotonic() >= deadline - .1 or abort.is_set() or stop.is_set()):
                        break  # Partial requests are deliberately excluded.
                    else:
                        raise ValueError('upload_failed')
        except Exception:
            failures.append('upload_failed')
            abort.set()
        finally:
            if process is not None and process.poll() is None:
                process.kill(); process.wait()

    workers = [threading.Thread(target=transfer, args=(i,)) for i in range(streams)]
    for worker in workers:
        worker.start()
    error = ''
    while any(worker.is_alive() for worker in workers):
        try:
            temps = temperature()
            if temps:
                peak = max(([peak] if peak is not None else []) + temps)
            if stop.is_set():
                error = 'cancelled'
            elif peak is not None and peak >= 75:
                error = 'temperature_limit'
            if error:
                abort.set()
        except Exception:
            error = 'upload_failed'; abort.set()
        abort.wait(.1) if not abort.is_set() else time.sleep(.02)
    for worker in workers:
        worker.join()
    elapsed = time.monotonic() - start
    total = sum(counts)
    error = error or (failures[0] if failures else '') or ('upload_failed' if not total else '')
    return {'upload_mbps': None if error else round(total * 8 / elapsed / 1e6, 2),
            'upload_mb': round(total / 1e6, 1), 'upload_seconds': round(elapsed, 2),
            'upload_server': 'Cloudflare · HTTPS', 'upload_error': error,
            'upload_peak_c': peak}
