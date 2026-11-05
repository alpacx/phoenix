# Progresso — 2026-11-05

## Verificato sul computer

Cartella inizialmente vuota, nessun AGENTS.md trovato. SDK locale 5.5.4 commit
10ca0dff2f40aeb539f22d1ef88d031cf7421743, toolchain esp-14.2.0_20260121.
Build/link P4 v1.x riusciti; build-lab con USB interamente collegata riuscita,
immagine 0x92350 byte al checkpoint precedente all'identificazione hardware.
Test C con UBSan passati: firewall/gate, parsing, MSS, 100000 pacchetti malformati;
WireGuard parser e 20000 profili malformati. Non sono test end-to-end del gateway.
ASan non verificato: anche un main vuoto resta in CPU busy nell'ambiente; processi
ferm ati e ripiegato su UBSan. Nessun risultato ASan dichiarato.

## Hardware

Scheda ora collegata. Porta /dev/cu.usbmodem5B901859211, bridge 1A86:55D3;
esptool identifica ESP32-P4 v3.1, quarzo 40 MHz. Richiesti backup completo e
build separata v3.x, in corso al momento di questo checkpoint.
Nessun eFuse modificato, nessuna rete del Mac cambiata.

## Limiti reali

Nessuna misura throughput/latenza/RAM sotto traffico ancora effettuata.
USB dati necessita verifica fixture VBUS; non usare un cavo generico host-host.
VPN integrata e compilata ma handshake/server e gateway client non ancora provati.
Wi-Fi/AP, profili multipli, OTA firmata e altre attività in TASKS.md non implementate.
Touch escluso. Ulteriori dettagli e risultati verranno aggiornati dopo le prove.
