# Verifiche del port Linux — 2026-11-11

## Risultato corrente

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

## Riproduzione

Dalla root:

```sh
./tools/test-linux.sh
./tools/test.sh
./tools/test-history.sh
node tests/test_countdown.cjs
./tools/build.sh -B build-admin -D SDKCONFIG=build-admin/sdkconfig

docker build -t phoenix-linux-test:local -f platforms/linux/tests/integration/Dockerfile platforms/linux/tests/integration
docker run --rm --cap-add NET_ADMIN --mount type=bind,source="$PWD",target=/workspace,readonly phoenix-linux-test:local
docker run --rm --cap-add NET_ADMIN --mount type=bind,source="$PWD",target=/workspace,readonly phoenix-linux-test:local python3 platforms/linux/tests/integration/check_deploy.py
python3 platforms/linux/tests/integration/traffic.py
```

La prova traffico richiede subnet Docker 192.168.9.0/24 e 192.0.2.0/24 libere;
pulisce solo risorse phoenix-test con identificatore casuale. Chiavi effimere,
nessun segreto stampato. Nessun nftables/routing applicato al Mac.

VM (host Docker ARM64, QEMU TCG, alcuni minuti e spazio per disco temporaneo):

```sh
docker build -t phoenix-systemd-lab:local -f platforms/linux/tests/vm/Dockerfile platforms/linux/tests/vm
docker run --rm --mount type=bind,source="$PWD",target=/workspace,readonly phoenix-systemd-lab:local sh platforms/linux/tests/vm/build_and_run.sh
```

Lo script fallisce se manca il marcatore finale di successo. Le chiavi di test
restano nel filesystem temporaneo del container/guest eliminato alla fine.
Il workflow `.github/workflows/software.yml` automatizza test Python, contratti,
C portabile, JS e traffico Linux; non è ancora stato eseguito da GitHub perché
queste modifiche non sono state pubblicate. VM e build ESP-IDF sono prove locali.

## Gate fisici e di produzione

Restano: avvio immagine reale, AP/STA/driver, DHCP/DNS/IPv6 dei client, USB device
e cablaggio, NordVPN con abbonamento, IP pubblico del tunnel, throughput,
temperature, consumi ed endurance. Occorrono inoltre audit di sicurezza completo,
gestione operativa certificati/chiavi e prove di storage/power loss.
Non dichiarare il prodotto pronto sulla sola base di questi test virtuali.

## Revisione e prove prolungate successive

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

Riproduzione del test prolungato (30–1200 secondi):

```sh
PHOENIX_SOAK_SECONDS=600 python3 platforms/linux/tests/integration/traffic.py
```

Il controllore rimane nello stesso processo mentre vengono ricreati i tunnel,
inoltrato traffico HTTP, rimosso il tunnel e verificate le modalità bloccata e
diretta. Le riconnessioni di questa prova sono esplicite; i ritentativi temporizzati
sono verificati separatamente. Non sono rotazioni geografiche NordVPN reali.
Memoria RSS e descrittori sono misurati dopo riscaldamento; nessuna stima della
velocità o RAM totale della ROCK si ricava da questi dati.

Per i browser avviare `tests/integration/ui_harness.py` nel container dedicato,
con sola porta host 127.0.0.1:18086 pubblicata (vedere workflow software.yml).
La credenziale di quel banco è pubblica/fittizia: **non inserirvi account reali**.
Installare le dipendenze di test in un ambiente Python dedicato:

```sh
python3 -m pip install -r platforms/linux/tests/browser/requirements.txt
python3 -m playwright install chromium webkit firefox
PHOENIX_BROWSER=chromium python3 platforms/linux/tests/browser/review.py
PHOENIX_BROWSER=webkit python3 platforms/linux/tests/browser/review.py
PHOENIX_BROWSER=firefox python3 platforms/linux/tests/browser/review.py
```

Le risorse Docker di test vengono rimosse al termine. Account NordVPN reale
escluso su scelta esplicita dell’utente; nessuna credenziale necessaria è stata
richiesta in chat o recuperata da altri servizi.

Risultato acquisito: **605 secondi, 102 cicli**, RSS del controllore dopo
riscaldamento **22144–22144 KiB**, descrittori **4–4**. Nessun fallimento di
connettività attesa nelle fasi verificate. Questo non esclude perdite di memoria
su tempi maggiori o con carichi diversi. Report locale: results/linux/review-report.json.
