# Baseline TCP Ethernet Waveshare ESP32-P4-NANO

Firmware autonomo: nessuna USB device, Wi-Fi, NAT, firewall o VPN. Usa i GPIO
IP101 verificati nel progetto. DHCP automatico; log UART della velocità/duplex.
Server TCP 5001 senza autenticazione, esclusivamente per banco su LAN fidata.
U riceve e conferma il conteggio; D invia. 32 MiB per connessione, timeout socket
10 secondi e limite ciclo 60 secondi. Non misura integrità applicativa o jitter.

Build dalla radice:

```sh
IDF_TARGET=esp32p4 ./tools/build.sh -C benchmarks/ethernet -B benchmarks/ethernet/build
```

Flash completo tramite flash_args nella directory di build, dopo identificazione
P4 >=3.0. App factory a 0x10000: non usare gli offset OTA Phoenix. Nessun eFuse.
Leggere l’indirizzo DHCP su UART, quindi dalla stessa LAN:

```sh
python3 benchmarks/ethernet/client.py INDIRIZZO_DHCP
```

Tre trasferimenti per direzione; Mbit/s basati sul payload e tempo monotono del
Mac. U include conferma del ricevente, D conta tutti i byte ricevuti sul Mac.
Tempi UART D possono escludere la coda TX residua: preferire la misura client.
I risultati includono rete/router e collegamento Mac (eventualmente Wi-Fi).
Non equivalgono a velocità PHY, USB, forwarding o WireGuard. Config TCP default
ESP-IDF, CPU 400 MHz, compilazione -O2. Nessuna modifica alle route del Mac.

## Esito iniziale 2026-11-06

Link 100 Mbit/s full-duplex; DHCP 192.168.8.170/24 via 192.168.8.1.
Mac 192.168.1.179/24 via 192.168.1.1: TCP 5001 timeout dopo 10 secondi.
Nessun valore di throughput ottenuto. Collegare i due dispositivi alla stessa LAN.

## Nuova prova completata

Mac -> P4: 14.27 Mbit/s aggregati, intervallo 13.94–14.68.
P4 -> Mac: 8.91 Mbit/s aggregati, intervallo 8.47–9.17.

Tre trasferimenti da 32 MiB per direzione, tutti completi. File risultati:
results/ethernet-retry2-client.jsonl. Nessuna VPN. Buffer TCP default 5760 byte;
risultato include il collegamento Mac e la LAN, non è un limite hardware.

## Variante TCP con buffer aumentati

Per confronto controllato, stessi sorgenti/CPU/PHY e protocollo; cambiano solo
send buffer e receive window (5760 -> 63360 byte) e code di ricezione TCP
(6 -> 46) e tcpip (32 -> 64). Nessun window scaling, PSRAM o cambio DMA.

```sh
IDF_TARGET=esp32p4 ./tools/build.sh -C benchmarks/ethernet \
  -B benchmarks/ethernet/build-tuned \
  -D SDKCONFIG="$PWD/benchmarks/ethernet/build-tuned/sdkconfig" \
  -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.tuned'
```

Aprire il monitor seriale PRIMA del test: sul banco è stato osservato un riavvio
all’apertura. Attendere DHCP, poi mantenere stabile la connessione seriale fino
al termine. Misurare con lo stesso client tre trasferimenti per direzione.

## Risultato variante con buffer aumentati

| Direzione | Default Mbit/s | Buffer aumentati Mbit/s | Miglioramento |
|---|---:|---:|---:|
| Mac → P4 | 14.27 | 74.54 | 5.22× |
| P4 → Mac | 8.91 | 38.98 | 4.38× |

Media aggregata = bit totali / tempo totale, tre trasferimenti da 32 MiB per
direzione. Tutti completi. Intervalli: U 63.61–82.49, D 34.11–42.55 Mbit/s.
Log results/ethernet-tuned-client.jsonl e results/ethernet-tuned-uart.log.
Test sequenziale su LAN condivisa: nessuna garanzia di isolamento delle condizioni
radio/rete. Nessuna VPN/USB/forwarding inclusa. Firmware tuned lasciato sulla P4.
