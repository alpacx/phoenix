# Benchmark locale ChaCha20-Poly1305 sulla Waveshare P4

Misura il costo delle primitive usate da Phoenix, non il throughput WireGuard.
Non inizializza USB, Ethernet, Wi-Fi o NVS; chiave e dati sono sintetici pubblici.
Build autonoma per P4 >=3.0, 400 MHz, -O2, task CPU0, buffer in RAM interna.
Richiede SDK e componente libsodium già presenti nel progetto principale.

Dalla radice:

```sh
IDF_TARGET=esp32p4 ./tools/build.sh -C benchmarks/crypto -B benchmarks/crypto/build
```

Prima del flash identificare la scheda e controllare secure boot / flash encryption
disabilitati. Il firmware usa una propria tabella partizioni: il flash completo
sostituisce bootloader, tabella e app (factory 0x10000). Non è un aggiornamento OTA
Phoenix. Usare flash_args nella directory di build e la porta della P4 identificata.

Acquisizione UART:

```sh
~/.espressif/python_env/idf5.5_py3.9_env/bin/python tools/monitor.py \
  --port /dev/cu.usbmodem5B901859211 --reset --seconds 20
```

Tre ripetizioni di 1000 pacchetti per 64, 512 e 1424 byte. Ogni cifratura usa
un nonce diverso nella sessione; decifratura confrontata al plaintext originale.
Un tag alterato deve essere rifiutato per ogni ripetizione. Le assert sono attive.
Mbit/s = payload_bytes * 8 * count / microsecondi. Il timer include overhead di
misura; esclude pause scheduler, confronto dati e controllo tag alterato.
Le misure encrypt e decrypt sono separate, non una somma di banda simultanea.

## Misura 2026-11-06

| Payload | Encrypt Mbit/s | Decrypt Mbit/s |
|---|---:|---:|
| 64 | 24.51–24.80 | 25.02–25.19 |
| 512 | 46.54–46.57 | 46.67–46.70 |
| 1424 | 49.62–49.63 | 49.70–49.72 |

Log: results/crypto-benchmark.log dalla radice. Roundtrip/tag checks passati.
Heap stabile 594640 byte dopo il primo campione. Non è uno stress test memoria.
Il risultato riguarda questa implementazione a un task: non esclude miglioramenti
con altre implementazioni o parallelismo e non predice le prestazioni dell’S31.
La rete completa aggiunge lavoro; Ethernet IP101 della scheda è 10/100.
Per il passo successivo collegare Ethernet e predisporre un peer di test locale;
la USB device necessita ancora del cablaggio verificato in docs/HARDWARE.md.
