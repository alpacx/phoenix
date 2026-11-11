# Phoenix — gateway multi-piattaforma

Gateway sperimentale, non ancora un prodotto validato. Backend ESP32 esistente;
port Linux per ROCK 4C+ in preparazione. Il codice operativo descritto sotto è
quello ESP32, non una dichiarazione di funzionalità già disponibili su Linux.

## Organizzazione

- [ESP32 / ESP-IDF](platforms/esp32/README.md): sorgenti in `platforms/esp32/main/`.
- [Linux / ROCK](platforms/linux/README.md): piano del backend Linux.
- `shared/web/`: pannello amministrativo comune.
- `shared/phoenix_core/`: logica C portabile.
- [Mappa del progetto](docs/PROJECT_STRUCTURE.md) e [istruzioni agenti](AGENTS.md).
- `hardware/phoenix-g1/`: progettazione della scheda custom, ancora incompleta.

Implementati: Ethernet IP101/RMII con DHCP, USB HS CDC-NCM con DHCP/NAT IPv4,
firewall L3/L4, API amministrativa locale e pannello, importatore WireGuard IPv4
full tunnel e blocco in uscita, gestione C6 STA/AP e aggiornamento firmato in software. La presenza del codice e una build riuscita non
provano il funzionamento sul banco: consultare PROGRESS.md.

## Build

ESP-IDF 5.5.4, commit esatto `10ca0dff2f40aeb539f22d1ef88d031cf7421743`.
Dipendenze registry e relativi hash in dependencies.lock. Toolchain installata:
`riscv32-esp-elf esp-14.2.0_20260121`. Script configurato per l'ambiente locale;
IDF_PATH e IDF_PYTHON_ENV_PATH sono sovrascrivibili.

```sh
./tools/test.sh
# Scheda rilevata v3.1; USB dati spento:
./tools/build.sh -B build-rev3 -D SDKCONFIG=build-rev3/sdkconfig \
  -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.rev3'
# Solo compilazione del percorso USB, NON certifica il cablaggio:
./tools/build.sh -B build-usb-rev3 -D SDKCONFIG=build-usb-rev3/sdkconfig \
  -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.rev3;sdkconfig.lab;sdkconfig.signed'
```

La variante firmata richiede prima la chiave descritta in [OTA](docs/OTA.md).

Il default sdkconfig.defaults supporta P4 v1.x; non caricarlo sulla v3.1.
Per una build USB di banco v3.x aggiungere sdkconfig.lab DOPO sdkconfig.rev3
in una cartella di build nuova. Non modificare i file SDK globali.

## Cablaggio e flash

Leggere [HARDWARE.md](docs/HARDWARE.md). La USB-C è seriale/alimentazione; la
Type-A è OTG e porta VBUS generata dalla scheda. Non collegare un generico
cavo host-host. USB dati resta disattivata per default.

Il backup originale è locale, riservato e ignorato da Git:
`results/recovery/original-flash.bin`. Non distribuirlo: può contenere dati
preesistenti. Per ripristinare, dopo aver identificato nuovamente la stessa
scheda e verificato hash/dimensione:

```sh
# Da ambiente ESP-IDF attivato. PORT deve essere la P4 dedicata identificata.
python -m esptool --chip esp32p4 --port "$PORT" write_flash 0 results/recovery/original-flash.bin
```

Non modificare eFuse. Nessuna flash encryption/secure boot irreversibile attivata.
BOOT+RESET è la via ROM di recupero; BOOT condivide GPIO35 con Ethernet TXD1:
non usarlo come pulsante dell'interfaccia durante il traffico.

## Uso sperimentale

USB LAN: 192.168.7.1/24, DHCP, pannello http://192.168.7.1/. Nessun servizio
amministrativo accettato dall'uplink. Pairing via UART nei primi 120 secondi:
`pair ` seguito da 64 caratteri esadecimali casuali, mai riportati nei log.
Il token rimane solo nel client; la scheda conserva SHA-256 in NVS.
`time <epoch UNIX di 10 cifre>` imposta l'orologio nello stesso intervallo.
Il pannello conserva il token soltanto nel campo della pagina.

All'avvio il traffico inoltrato è bloccato. La modalità diretta è una scelta
esplicita via API. WireGuard resta chiuso finché non esiste una sessione valida.
Il dispositivo non controlla il traffico del Mac sulle altre interfacce.
Non è un antivirus, un IDS completo o uno strumento di ispezione HTTPS.

[API](docs/API.md) · [Architettura](docs/ARCHITECTURE.md) ·
[Prove](docs/TESTING.md) · [Dipendenze](docs/DEPENDENCIES.md) ·
[Attività](TASKS.md) · [Ripresa](NEXT_SESSION.md)
