# Phoenix Linux

Backend di ingegneria per Linux ARM64. Testato su Debian 12 in container e in
una VM QEMU con systemd reale; installato sulla ROCK 4C+ con prime verifiche
fisiche di servizi, AP, aggiornamento firmato e forwarding Ethernet.
Vedere [bring-up](boards/rock4c-plus/BRINGUP.md) per risultati e limiti.
La ROCK usa RK3399, distinto dal RK3562 della scheda custom.

## Architettura

Un solo binario statico Rust `phoenix` (musl, aarch64), sorgente in
[rust/](rust/README.md), unità systemd in [deploy/](deploy/README.md). Moduli
principali (`rust/src/`):

- `frontend.rs`, `http.rs`, `auth.rs`: UI unica `shared/web` inclusa nel
  binario, HTTPS loopback sulla porta 8443, password con cambio obbligatorio e
  Bearer per l'API; frontend eseguito come `phoenix-web`, senza capability.
- `rpc.rs`, `local_api.rs`: socket Unix con verifica UID del peer, richieste
  limitate e comandi ammessi esplicitamente. Nessuna API per shell, argv o
  lettura di file arbitrari.
- `control.rs`, `controller.rs`: worker privilegiato, configurazione, comandi
  asincroni, rotazione, paese fisso, esclusioni e ritentativi 5–60 secondi.
- `runtime.rs`, `firewall.rs`, `policy.rs`: nftables/WireGuard kernel, blocco
  prima delle transizioni, NAT e port forwarding; nessun fallback diretto.
- `uplink_http.rs`, `httpc.rs`, `nord.rs`: DoH e HTTPS vincolati all'interfaccia
  selezionata. DNS/API NordVPN non dipendono dalla route Ethernet di gestione.
- `usb_gadget.rs`, `lan.rs`: gadget ECM/NCM opt-in e DHCP USB;
  [attivazione e limiti](deploy/USB_ETHERNET.md).
- `lan.rs`, `station.rs`, `access_point.rs`: AP/DHCP e STA NetworkManager
  opt-in; profili propri, controllo ownership e recupero dopo arresto.
- `store.rs`, `vault.rs`, `history.rs`: configurazione transazionale (SQLite),
  file privati e storico delle connessioni confermate per otto ore.
- `updates.rs`, `install.rs`, `package.rs`: installatore, bundle allowlisted,
  firma Ed25519, sequenza monotona e rollback applicativo; bootstrap indipendente.
- `stop_guard.rs`: blocco su stop/crash. `preflight.rs`: inventario read-only.

Il binario gestisce il control plane; i pacchetti transitano nel kernel. Attivo
sulla ROCK dal 18/11/2026: 2,4 MB RSS il worker e 1,6 MB il frontend, contro
24 + 24 MB della precedente implementazione Python, rimossa dal repository
(resta nella storia git). ESP32 resta indipendente e funzionante. Nessun SDK
ESP-IDF viene importato nei servizi Linux.

## Installazione e verifiche

[Immagine ROCK](boards/rock4c-plus/README.md) · [Installazione](deploy/README.md) ·
[Aggiornamenti](deploy/UPDATES.md) · [API](API_STATUS.md) · [Evidenze](VALIDATION.md) · [Revisione sicurezza](SECURITY_REVIEW.md)

Dalla root (solo Docker sul Mac): `./tools/test-linux.sh` per i test unitari;
build, bundle e test in container nel [README Rust](rust/README.md). Sul target:
`phoenix preflight` (inventario read-only, exit 2 se ci sono blocchi).

Solo per sviluppo locale senza rete operativa resta il server HTTP
monoprocesso su loopback: `phoenix control --state-dir /tmp/phoenix-linux-local`
(porta 8085, token nel file indicato all'avvio). Non è il deployment HTTPS
separato; non usarlo come servizio di produzione.

## Limiti residui

Prove fisiche AP/STA, USB device/cablaggio, DHCP/DNS dei client, abbonamento
NordVPN, throughput, consumi e temperature richiedono il target. Sono stati
provati un catalogo pubblico NordVPN reale e tunnel WireGuard locali; ciò non
prova un account NordVPN o le prestazioni della ROCK.

La VM verifica systemd, credenziali, privilegi, aggiornamento, rollback e reboot;
non simula un'interruzione elettrica durante una scrittura su microSD.
Il frontend è accessibile solo tramite loopback/SSH, con certificato locale da
verificare e rendere attendibile. Non c'è ancora esposizione HTTPS diretta su AP.
Un audit di sicurezza completo e prove di endurance restano necessari prima
della produzione. Nessuna chiave di firma di produzione è stata generata.

## Aggiornamento banco USB — 2026-11-15

CDC-ECM, DHCP e navigazione VPN via USB verificati. Accesso web diretto con
password e cambio obbligatorio: [USB_ADMIN.md](deploy/USB_ADMIN.md). Le note
offline precedenti non sostituiscono queste evidenze. VBUS/bootloader restano
non qualificati; eccezione USB valida solo per il boot corrente.
