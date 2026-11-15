# Struttura del progetto Phoenix

Aggiornata: 2026-11-11. Due piattaforme software, un prodotto e una UI.

| Percorso | Responsabilità / stato |
|---|---|
| `platforms/esp32/main/` | Backend ESP-IDF esistente, NVS e controllo hardware |
| `platforms/linux/` | Backend Linux, frontend HTTPS non root e worker RPC; test Docker, VM e primo deployment fisico ROCK |
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
- Linux: backend installato sulla ROCK; servizi, AP, aggiornamento firmato e forwarding Ethernet verificati. Vedere platforms/linux/VALIDATION.md e API_STATUS.md.
- Hardware custom: progetto incompleto; checkpoint corrente in
  `hardware/phoenix-g1/migration-rk3562/experiments/pmic-ldo-inputs/working-candidate.json`.
- Flash eMMC integrata nello schema e nel PCB di lavoro, con masse esterne instradate:
  `hardware/phoenix-g1/migration-rk3562/experiments/emmc-system/`, con collegamenti
  di alimentazione candidati; fanout, rail, segnali e qualifica restano aperti.

Per il checkpoint hardware, usare il Python di KiCad per
`hardware/phoenix-g1/tools/audit_pmic_ldo_inputs.py` e
`hardware/phoenix-g1/tools/test_pmic_ldo_input_audit.py`; il README del checkpoint
elenca la ricostruzione completa. I test CAD non richiedono build o flash software.

Registrare nuove evidenze distinguendo codice, build, audit CAD e prove fisiche.

## Verifica della riorganizzazione — 2026-11-11

Passati: test host firewall/profili/USB sync/rotazione/policy, test storico,
test countdown e build completa ESP-IDF con configurazione build-admin.
I sorgenti spostati sono identici alla revisione precedente, salvo il CMake
del componente per aggiornare i percorsi. Nessun flash o test fisico eseguito
in questa riorganizzazione; backend Linux ancora da implementare.

## USB Ethernet Linux — provisioning opt-in

`platforms/linux/service/phoenix_linux/usb_gadget.py` gestisce soltanto il gadget
configfs Phoenix, tramite unità separata `phoenix-usb-gadget.service`. Il worker
usa `usb_lan.py` per DHCP e le policy USB preesistenti per il traffico. Configurazione
e procedura in `platforms/linux/deploy/USB_ETHERNET.md`. Non attivare senza
identificare UDC/target e verificare fisicamente VBUS; nessun cambio automatico
di ruolo o regolatori. Test configfs simulati distinti dal DHCP reale su veth
in `platforms/linux/tests/integration/check_usb_dhcp.py`; nessuna prova USB
fisica implicita nei risultati Docker.
