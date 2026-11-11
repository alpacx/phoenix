# Struttura del progetto Phoenix

Aggiornata: 2026-11-11. Due piattaforme software, un prodotto e una UI.

| Percorso | Responsabilità / stato |
|---|---|
| `platforms/esp32/main/` | Backend ESP-IDF esistente, NVS e controllo hardware |
| `platforms/linux/` | Backend Linux, frontend HTTPS non root e worker RPC; test Docker e VM systemd, non ancora su ROCK |
| `shared/web/` | Unica sorgente HTML/CSS/JS e catalogo paesi del pannello |
| `shared/phoenix_core/` | C portabile: policy, firewall, profili WG, rotazione |
| `components/wireguard/` | Implementazione WireGuard embedded, non backend Linux |
| `components_overrides/` | Override ESP-IDF/TinyUSB verificati |
| `tests/` | Test host core, UI e adattatori ESP32 con stub |
| `tools/` | Build/test delle due piattaforme e utilità di banco |
| `.github/workflows/software.yml` | CI Python/contratti, C portabile, JS, traffico Linux e browser; da pubblicare |
| `benchmarks/` | Prove e strumenti di misura; non servizi di produzione |
| `docs/` | API, architettura, hardware, procedure e mappa repository |
| `hardware/phoenix-g1/` | Progettazione elettronica custom, separata dal software |
| `results/`, `build*/`, `.tools/` | Artefatti locali ignorati; possono contenere segreti |

## Compatibilità di build

La root rimane un progetto ESP-IDF. Il CMake registra esplicitamente il
componente `main` spostato e il core condiviso; i nomi dei componenti rimangono
`main` e `phoenix_core`. Manifest, Kconfig e hook lwIP restano collegati alla
build. Gli asset web sono incorporati dal percorso condiviso, conservando
i simboli binari utilizzati dall'HTTP server.

Per questo primo passo non si spostano configurazioni SDK, partizioni,
dipendenze vendorizzate, benchmark o script di flash. Non cambiano i comandi
pubblici. Non si convertono automaticamente NVS o credenziali in file Linux.

## Contratto comune e differenze

`docs/API.md` è il punto di partenza documentale; il port deve mantenerlo allineato
con `admin_api.inc` e le chiamate della UI perché può non coprire tutte le
estensioni recenti. L'API comune va consolidata con test di contratto durante
il port, non considerata già certificata.

Condividere impostazioni e semantica (ordine regole, default deny, rotazione,
paese fisso, esclusioni, storico), non obbligatoriamente il dataplane.
Su Linux le policy verranno tradotte in nftables e WireGuard kernel;
su ESP32 restano lwIP e le implementazioni embedded.
Le capacità dovranno essere dichiarate dal backend: niente promesse USB o
throughput basate solo sul processore. La UI deve restare agnostica dall'hardware.

## Verifica delle modifiche

Dalla root:

```sh
./tools/test-linux.sh
./tools/test.sh
./tools/test-history.sh
node tests/test_countdown.cjs
./tools/build.sh -B build-admin -D SDKCONFIG=build-admin/sdkconfig
```

Il test storico richiede cJSON dell'ESP-IDF locale. L'ultimo comando usa la
configurazione di banco già presente e non esegue flash; su un nuovo checkout
scegliere esplicitamente il profilo seguendo README.md.
La build non prova rete, VPN, cablaggio, USB o prestazioni fisiche.

## Stato e ripresa

- ESP32: implementazione esistente; prove pregresse in NEXT_SESSION.md e PROGRESS.md.
- Linux: backend implementato e testato in Docker; avvio ROCK in attesa del supporto di storage. Vedere platforms/linux/VALIDATION.md e API_STATUS.md.
- Hardware custom: progetto incompleto; checkpoint corrente in
  `hardware/phoenix-g1/migration-rk3562/experiments/lpddr4-1gb/working-board.json`.
- Flash SPI NOR presente nel PCB; eMMC solo candidata, non integrata.

Registrare nuove evidenze distinguendo codice, build, audit CAD e prove fisiche.

## Verifica della riorganizzazione — 2026-11-11

Passati: test host firewall/profili/USB sync/rotazione/policy, test storico,
test countdown e build completa ESP-IDF con configurazione build-admin.
I sorgenti spostati sono identici alla revisione precedente, salvo il CMake
del componente per aggiornare i percorsi. Nessun flash o test fisico eseguito
in questa riorganizzazione; backend Linux ancora da implementare.
