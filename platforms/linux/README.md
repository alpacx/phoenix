# Phoenix Linux

Backend di ingegneria per Linux ARM64. Testato su Debian 12 in container e in
una VM QEMU con systemd reale; **non ancora validato sulla ROCK 4C+**.
La ROCK usa RK3399, distinto dal RK3562 della scheda custom.

## Architettura

- `frontend.py`, `server.py`: UI unica `shared/web`, API Bearer, HTTPS loopback
  sulla porta 8443; frontend eseguito come `phoenix-web`, senza capability.
- `rpc.py`: socket Unix con verifica UID del peer, richieste limitate e comandi
  ammessi esplicitamente. Nessuna API per shell, argv o lettura di file arbitrari.
- `controller.py`: worker privilegiato, configurazione, comandi asincroni,
  rotazione, paese fisso, esclusioni e ritentativi 5–60 secondi.
- `runtime.py`, `firewall.py`, `policy.py`: nftables/WireGuard kernel, blocco
  prima delle transizioni, NAT e port forwarding; nessun fallback diretto.
- `uplink_http.py`, `nord.py`: DoH e HTTPS vincolati alla stessa interfaccia
  selezionata. DNS/API NordVPN non dipendono più dalla route Ethernet di gestione.
- `lan.py`, `station.py`, `access_point.py`: AP/DHCP e STA NetworkManager opt-in;
  profili propri, controllo ownership e recupero dopo arresto del servizio.
- `store.py`, `vault.py`, `history.py`: configurazione transazionale, file
  privati e storico delle connessioni confermate per otto ore.
- `updates.py`, `install.py`, `package.py`: installatore, bundle allowlisted,
  firma Ed25519, sequenza monotona e rollback applicativo; bootstrap indipendente.
- `stop_guard.py`: blocco su stop/crash. `preflight.py`: inventario read-only.

Python gestisce il control plane; i pacchetti transitano nel kernel. ESP32 resta
indipendente e funzionante. Nessun SDK ESP-IDF viene importato nei servizi Linux.

## Installazione e verifiche

[Immagine ROCK](boards/rock4c-plus/README.md) · [Installazione](deploy/README.md) ·
[Aggiornamenti](deploy/UPDATES.md) · [API](API_STATUS.md) · [Evidenze](VALIDATION.md) · [Revisione sicurezza](SECURITY_REVIEW.md)

Dalla root:

```sh
./tools/test-linux.sh
PYTHONPATH=platforms/linux/service python3 -m phoenix_linux.preflight
```

Solo per sviluppo locale senza rete operativa, resta disponibile il server
HTTP monoprocesso su loopback: `PYTHONPATH=platforms/linux/service python3 -m
phoenix_linux.server --state-dir /tmp/phoenix-linux-local`. Non è il deployment
HTTPS separato; non usare questo comando come servizio di produzione.

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
