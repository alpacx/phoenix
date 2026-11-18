# Verifiche del backend Linux

## Servizi Rust — 2026-11-18 (risultato corrente)

Implementazione Python rimossa; tutte le prove seguenti usano il binario Rust
`phoenix`. Host Docker aarch64 (Apple Silicon); la CI GitHub (x86_64) non è
ancora stata eseguita perché il workflow non è pubblicato.

- **Unit e parità** (`./tools/test-linux.sh`): 143 test + 5 di parità con
  l'output congelato dell'implementazione Python; 6 test kernel ignorati qui.
- **Container kernel** (`./tools/rust-kernel-tests.sh`): 6 test `kernel_*`
  (nft/ip/wg/conntrack, DHCP reale dnsmasq ↔ udhcpc su veth, `dnsmasq --test`,
  stop guard, NetworkManager reale che carica il keyfile STA senza radio,
  DoH+TLS solo via uplink scelto e nessun ripiego dopo caduta del link) e
  `systemd-analyze verify` di 9 unità.
- **Black-box pacchetti** (`rust_blackbox.py`): tre container, solo API HTTPS:
  login/cambio password/Origin, blocco iniziale, NAT diretto, revisione e
  conflitto policy, deny ordinato, port forwarding con default deny e filtro
  sorgente, tunnel WireGuard reale con handshake e storico, perdita del tunnel
  e disconnessione senza fallback, arresto con forwarding a 0 e stop guard.
  Soak 60 s: 7 cicli, RSS worker 2764–2776 KiB, descrittori 4–6.
  RSS dopo lo scenario: worker 2768 KiB (anon 152), frontend 2092 KiB (anon 104).
- **Browser** (Playwright 1.51 in Docker, servizi Rust in container): Chromium,
  WebKit e Firefox su 7 pagine a 1440/390/320 px senza overflow, roundtrip
  policy e forwarding, banner offline, logout che svuota i campi sensibili,
  login errato, reload con sessione attiva senza comparsa del login, nessun
  errore JS; flusso password con cambio obbligatorio,
  reload, logout, vecchia password rifiutata e blocco dopo 3 errori.
- **VM QEMU ARM64 con systemd** (190 s): `phoenix install`, avvio reale delle
  unità, frontend non root con CapEff zero, certificato CA:FALSE accettato come
  trust anchor, 401/403 su token e Origin errati, token illeggibile per
  phoenix-web, SIGKILL del worker → forwarding 0 e stop guard, poi recupero;
  upload firmato formato 2 con switch e health check, cinque aggiornamenti
  consecutivi, replay rifiutato, release non avviabile → rollback e traffico
  bloccato, stop guard, journal interrotto recuperato dopo **vero reboot**.
  RSS nella VM: worker 2424 KiB, frontend 1520 KiB.
- **ROCK 4C+**: servizi Rust attivi dal 18/11; aggiornamento firmato formato 2
  caricato dal pannello e attivato (release `11-5faa8de28eeb0f62`), vedere
  [BRINGUP](boards/rock4c-plus/BRINGUP.md).

Non provati: enumerazione USB, radio/AP reali in questi test, handshake con un
provider VPN reale, throughput, power loss durante scritture.

### Riproduzione (dalla root, solo Docker sul Mac)

```sh
./tools/test-linux.sh
./tools/rust-linux.sh build --release
docker build -t phoenix-linux-test:local -f platforms/linux/tests/integration/Dockerfile platforms/linux/tests/integration
./tools/rust-kernel-tests.sh
python3 platforms/linux/tests/integration/rust_blackbox.py [--soak 600]
```

La prova black-box richiede subnet Docker 192.168.9.0/24 e 192.0.2.0/24
libere e rimuove solo le proprie risorse; chiavi effimere, nessun segreto
stampato, nessun nftables/routing applicato al Mac.

VM (host Docker ARM64, QEMU TCG; lo script rifiuta un binario non aarch64):

```sh
docker build -t phoenix-systemd-lab:local -f platforms/linux/tests/vm/Dockerfile platforms/linux/tests/vm
docker run --rm --mount type=bind,source="$PWD",target=/workspace,readonly phoenix-systemd-lab:local sh platforms/linux/tests/vm/build_and_run.sh
```

Browser: passi del job `browser` in `.github/workflows/software.yml`
(`ui_harness.py start|reset|stop`, password di test in `PHOENIX_TEST_PASSWORD`,
solo per il container usa e getta; **non usare credenziali reali**).
Screenshot in results/linux/ui-review.

## Gate fisici e di produzione

Restano: avvio immagine reale, AP/STA/driver, DHCP/DNS/IPv6 dei client, USB device
e cablaggio, NordVPN con abbonamento, IP pubblico del tunnel, throughput,
temperature, consumi ed endurance. Occorrono inoltre audit di sicurezza completo,
gestione operativa certificati/chiavi e prove di storage/power loss.
Non dichiarare il prodotto pronto sulla sola base di questi test virtuali.

## Storico — implementazione Python (11–14 novembre 2026)

Le sezioni seguenti descrivono prove sull'implementazione Python, ora rimossa;
i comandi citati non esistono più. Restano come evidenza storica.

**68 test Python passati su Debian 12**; test C, storico e countdown JS passati;
build ESP-IDF build-admin riuscita. Nessun flash. Nessun test fisico ROCK.

### API, sicurezza e fault injection

- Validazione policy/profili, revisioni, persistenza, storico 8 ore, rotazione,
  paese fisso/esclusioni, API HTTP, auth/Origin e richieste malformate.
- Contratto dei campi letti dalla UI: risultati Linux confrontati con la UI e
  presenza dei corrispondenti encoder ESP32. Non equivale a una prova HTTP ESP32.
- Scritture concorrenti durante un comando: rifiuto immediato, senza mutazione dopo timeout.
- RPC con peer UID reale Linux: utente sbagliato e metodo arbitrario rifiutati.
- DNS indisponibile ripetuto: traffico bloccato, paese conservato, backoff limitato.
- Credenziali corrotte: avvio rifiutato senza esporne il contenuto. La barriera
  di rete precede il caricamento dello stato persistente sul target.
- Ed25519 reale: firma/metadati/payload alterati, chiave sbagliata e replay;
  staging, rollback, journal interrotto, upload HTTP e blocco di nuovi comandi.
- Installer: modello sbagliato, installazione esistente e import bootstrap.

### Kernel e traffico in container

Tre container su bridge dedicati, senza host networking o privileged, con NAT
Docker disabilitato: blocco iniziale, NAT diretto, regola deny, port forwarding
con default deny e filtro sorgente. Tunnel WireGuard reale, handshake e HTTP;
dopo rimozione del tunnel nessun fallback diretto. Anche routing uplink con
fwmark e tabella dedicata verificato.

Fixture HTTPS locale con certificato di test verificato: DoH e API attraverso
l'uplink scelto, mentre la route principale verso il resolver è bloccata.
Disattivando il link scelto la richiesta fallisce senza usare l'altra interfaccia.
La precedente simulazione con solo blackhole lasciava il server fixture sullo
stesso segmento raggiungibile via binding del socket: corretta la prova usando
perdita reale del link. Non era evidenza di traffico su un'altra interfaccia.

NetworkManager Debian reale genera e carica il profilo; nessuna radio simulata.
Configurazione dnsmasq, tabella nft stop guard e quattro unità systemd verificate.

### HTTPS pubblico senza account

Richiesta reale dal container con il nuovo trasporto: DoH su 1.1.1.1, TLS con
verifica certificato e catalogo pubblico api.nordvpn.com riusciti (150 paesi alla
prova). Nessun token o account usato. Non dimostra un tunnel NordVPN reale.

### VM QEMU ARM64 con systemd PID 1

Debian 12 e kernel Debian, due CPU emulate, 1 GiB RAM, disco temporaneo;
**nessuna interfaccia di rete esterna**, solo interfacce dummy interne.

Passati:

1. Installazione, avvio reale delle unità, worker root e frontend UID non root
   con CapEff zero; HTTPS e certificato specifico del target verificato.
2. Certificato non attendibile, token assente e Origin errato rifiutati; frontend
   impossibilitato a leggere il file privato del token. SIGKILL del worker:
   stop guard e riavvio automatico, traffico nuovamente bloccato.
3. Upload firmato, stop/start di entrambi i servizi, switch della release e
   health check HTTPS con identità della nuova release.
4. Release firmata deliberatamente non avviabile: rollback alla precedente,
   ripristino del pannello e traffico inizialmente bloccato.
5. Arresto e riavvio: forwarding disabilitato e stop guard nft presente.
6. Journal di attivazione interrotto e symlink alla release difettosa, seguito
   da **vero reboot della VM**: recovery prima dei servizi, precedente release
   ripristinata e sequenza anti-replay conservata.

Il reboot verifica il recupero dello stato persistente preparato; non è un
power cut durante I/O, né una prova di affidabilità della microSD.

### Revisione e prove prolungate successive

Vedere [SECURITY_REVIEW.md](SECURITY_REVIEW.md) per riscontri, correzioni e limiti.
La suite è salita a **68 test Python passati**. UI provata con Playwright 1.51
su Chromium, WebKit e Firefox, a 1440/390/320 px: sette pagine, regole firewall,
logout/accesso errato e layout senza overflow della pagina. La suite browser
comprende inoltre port forwarding, perdita/recupero dell’API e cancellazione
dei campi sensibili; risultati per motore in results/linux/ui-review.

La VM esegue ora cinque aggiornamenti firmati consecutivi, poi una release
non avviabile, rollback e recovery dopo reboot. Payload di test e chiavi effimere;
non è una prova di migrazione tra schemi dati diversi. Il workflow CI include
anche i tre browser, ma non è stato pubblicato o eseguito su GitHub.

Il controllore rimane nello stesso processo mentre vengono ricreati i tunnel,
inoltrato traffico HTTP, rimosso il tunnel e verificate le modalità bloccata e
diretta. Le riconnessioni di questa prova sono esplicite; i ritentativi temporizzati
sono verificati separatamente. Non sono rotazioni geografiche NordVPN reali.
Memoria RSS e descrittori sono misurati dopo riscaldamento; nessuna stima della
velocità o RAM totale della ROCK si ricava da questi dati.

Le risorse Docker di test vengono rimosse al termine. Account NordVPN reale
escluso su scelta esplicita dell’utente; nessuna credenziale necessaria è stata
richiesta in chat o recuperata da altri servizi.

Risultato acquisito: **605 secondi, 102 cicli**, RSS del controllore dopo
riscaldamento **22144–22144 KiB**, descrittori **4–4**. Nessun fallimento di
connettività attesa nelle fasi verificate. Questo non esclude perdite di memoria
su tempi maggiori o con carichi diversi. Report locale: results/linux/review-report.json.

### USB Ethernet offline — 14 novembre 2026

Aggiunti 11 test USB (modello configfs, lifecycle DHCP e integrazione controller).
Scambio DHCP reale su veth in Docker: offerta/ACK, indirizzo/router/DNS, cambio
DNS e rimozione indirizzo su stop verificati. Test kernel nftables/WireGuard
esistente superato nel container senza rete esterna. L’enumerazione USB, la
UDC/ruolo della ROCK, VBUS, macOS e prestazioni restano non verificati.

Suite Linux finale nel container: 85 test, 84 superati e 1 saltato perché manca
la dipendenza opzionale per la compatibilità OpenSSL 1.1.1. Nessun test USB
nuovo saltato. I test diretti sul Mac non sostituiscono questa esecuzione Linux.
