## Checkpoint clock Ethernet — 16 novembre 2026

Ripartire da `hardware/phoenix-g1/migration-rk3562/experiments/pmic-ldo-inputs/working-candidate.json`.
PCB `pcb/ethernet-clock-pins.kicad_pcb`: gruppo quarzo PHY riposizionato e collegato.
Y501 libera la riserva H8105; C520/C521 vicini al quarzo, masse e pin U5.36/37
collegati. L501 sul retro: layout del suo convertitore ancora da qualificare.
172 coppie, 51 test CAD passati; nessuna nuova violazione DRC. Due test ulteriori
verificano rollback e rilevamento dell'interferenza meccanica. 227 reti multi-pad
ancora aperte; non è una percentuale di completamento.
Ricostruzione: `hardware/phoenix-g1/tools/rebuild_local_copper.py` con Python KiCad.
Ristretto collo da 0,15 mm solo sui due segnali clock dentro il courtyard U5;
clearance invariate, regola confrontata esattamente nell'audit cumulativo.
19 possibili conflitti meccanici preesistenti restano aperti. Il tentativo R513
non è adottato. Contorno 90×40 mm, obiettivo 85×35 non qualificato.
Nessun nuovo MPN, ordine, commit/push o modifica ROCK. Nessuna qualifica elettrica,
termica, EMC o produttiva. Le sezioni seguenti sono storiche.

## Ripresa CAD dopo commit/push — 15 novembre 2026

Pubblicato fbcb7de su origin/master con alpacx, poi ripristinato Coqoonit.
Nuovo checkpoint locale pmic-ldo-inputs/pcb/five-volt-testpoint.kicad_pcb:
ingresso +5V_MAIN del convertitore CPU e TP3 collegati; audit 119 coppie,
20 test, nessuna nuova violazione DRC. Vedere RESUME.md del checkpoint.
VDC pin61, restante routing e qualifica elettrica/termica ancora aperti.
Le sezioni successive descrivono stati precedenti, non il checkpoint attuale.

## Hardware salvato; passaggio a prova USB ROCK — 15 novembre 2026

Leggere `hardware/phoenix-g1/migration-rk3562/experiments/pmic-ldo-inputs/RESUME.md`.
Checkpoint finale verificato: 117 coppie, 18 test, 233 reti aperte; non pronto alla produzione.

## Checkpoint gruppi alimentazione PMIC — 15 novembre 2026

Ripartire da `hardware/phoenix-g1/migration-rk3562/experiments/pmic-ldo-inputs/working-candidate.json`.
Nuovi: ingresso VCC_SPK_HP con C483, collegamenti fra gruppi PMIC su In4.Cu,
raccordo VCC1/VCC2, C481/C484, RTC e U4.66 (VCC4). Audit di 109 connessioni e tredici test passati; nessuna nuova
violazione DRC. +3V3_SYS ha cinque gruppi fisici; 234 reti multi-pad restano aperte.
U17 non alimenta ancora il gruppo PMIC. Portata delle piste/via, cadute di tensione
e dissipazione non qualificate; dettagli e ricostruzione nel README del checkpoint.
Il tentativo vcc9-link è rifiutato: non usarlo come base. Nessun nuovo componente, ordine, commit o push. I checkpoint sotto sono storici.

Il tentativo vcc9-link è rifiutato; non usarlo come base. Leggere anche
`pcb/startup-margin-review.json`: calcoli ideali e verifiche di avvio ancora aperte.

## Checkpoint ingressi PMIC VCC5/6/7/8 — 14 novembre 2026

Ripartire da `hardware/phoenix-g1/migration-rk3562/experiments/pmic-ldo-inputs/working-candidate.json`.
VCC5/6/7 collegati ai bypass; VCC8 unito al gruppo C425, C481 ancora aperto.
Preservato il regolatore di sistema completo localmente e il suo ingresso +5V_MAIN.
Audit: 97 coppie, cinque test di accettazione/interruzione passati, nessuna nuova
violazione DRC. Restano 234 reti multi-pad aperte. Vedere README pmic-ldo-inputs
per ricostruzione, collegamenti ancora aperti e limiti elettrici/termici/produttivi.
Nessun ordine o commit/push; i checkpoint sotto sono storici.

## Checkpoint regolatore di sistema — 14 novembre 2026

Ripartire da `hardware/phoenix-g1/migration-rk3562/experiments/system-3v3/working-candidate.json`.
Regolatore locale U17: potenza, masse, SS/PG/VOS e ingresso +5V_MAIN collegati.
Audit di 90 coppie, preservazione della baseline e test di interruzione superati.
Nessuna nuova violazione DRC; 234 reti multi-pad ancora aperte.
Distribuzione +3V3_SYS al PMIC e ingresso CPU ancora da completare.
Leggere il README system-3v3: geometria verificata, nessuna qualifica elettrica,
termica o produttiva. Nessun ordine o commit/push. I checkpoint sotto sono storici.

## Checkpoint alimentazione CPU e VCC3 — 14 novembre 2026

Ripartire da `hardware/phoenix-g1/migration-rk3562/experiments/startup-power/working-candidate.json`.
Collegati localmente VCC3, commutazione CPU, ingressi/bypass, tre condensatori d'uscita,
masse, feedback e enable locale. Audit di 64 coppie con preservazione della baseline.
Nessuna nuova violazione DRC: 125 avvisi residui, 236 reti multi-pad aperte.
La sorgente CPU, il rail PMU dell'enable e la distribuzione al SoC restano aperti:
non è una prova di accensione. Leggere il README startup-power per rigenerazione e limiti.
Nessun commit/push o ordine. I checkpoint sotto sono storici.

## Checkpoint H8103 e alimentazione display — 14 novembre 2026

Ripartire da `hardware/phoenix-g1/migration-rk3562/experiments/aux-mount-clear/working-candidate.json`.
Preserva i 25 collegamenti locali PMIC dello studio precedente.
H8103 ora è un foro NPTH M2 candidato: C1801/C1802 spostati vicino al regolatore U20,
R1815 spostato fuori dalla riserva. Sei connessioni LCD verificate, compreso ingresso al bus +5V_MAIN.
Enable e distribuzione display ancora aperti; non è una prova di funzionamento.
Nessuna nuova violazione DRC: rimangono 125 avvisi e 239 reti multi-pad aperte.
H8104/H8105, VCC3, routing generale e qualifica restano aperti; PCB ancora 90×40 mm.
Rigenerazione e limiti nel README di aux-mount-clear. Nessun commit/push in questa prosecuzione.
Le sezioni sotto documentano checkpoint precedenti.

## Checkpoint ingressi PMIC — 14 novembre 2026
Ripartire da `hardware/phoenix-g1/migration-rk3562/experiments/pmic-inputs/working-candidate.json`.
VCC1/C421, VCC2/C422 e VCC4/C424 collegati localmente; C422 ora sul fronte.
Dieci pin di massa PMIC collegati; tutte le istanze del pad esposto verificate.
Audit di 25 coppie e preservazione della baseline superati senza nuovi DRC.
Restano 125 avvisi e 239 reti multi-pad aperte: non è una scheda pronta.
Dettagli e riproduzione nel README di pmic-inputs; i checkpoint sotto sono storici.

## Checkpoint corrente aggiornato — BUCK5 e fissaggi, 14 novembre 2026

Ripartire da `hardware/phoenix-g1/migration-rk3562/experiments/pmic-buck5/working-candidate.json`,
non dalle prove fallite `io-escape`. Otto collegamenti locali BUCK5 connessi;
R1811/R431 e C422/C470 riposizionati; due fori NPTH da 2.2 mm realizzati
nel CAD a (53,4)/(83,3). C470 alimentazione/massa e C422 massa collegati;
C422.1 rimane aperto. Tre fissaggi ausiliari da risolvere. 125 avvisi via_dangling residui (14 avvisi serigrafia risolti),
239 reti multi-pad aperte. Non è un circuito alimentato o qualificato.
Leggere il README dello studio; rigenerazione transazionale `rebuild_pmic_buck5.py`.
La baseline eMMC resta conservata. Nessun commit/push o ordine in questa prosecuzione.

## Studio BUCK5 aggiunto — 14 novembre 2026

Checkpoint principale ancora `emmc-system/working-candidate.json`. Studio successivo
in `hardware/phoenix-g1/migration-rk3562/experiments/pmic-buck5/study-checkpoint.json`:
PCB feedback SHA `936b9c2acb270a35a0ff12be654f33cbac9b0e3d13730d67d80f3ee6cb172ba9`.
Induttore avvicinato al PMIC, bus J3 ripassato con continuità degli otto pin,
SW5, primo condensatore d'uscita, feedback e due ritorni di massa collegati.
Audit conserva 43 gruppi fisicamente connessi e non aggiunge DRC (139 rimangono).
Aperti U4.54→C425.1 e C445; leggere README dello studio prima di continuare.
Non è un'alimentazione completata o qualificata; non sostituire automaticamente
il checkpoint principale. Nessun commit/push eseguito per questa prosecuzione.

## Checkpoint corrente — 14 novembre, eMMC fisicamente integrata

- Usare `hardware/phoenix-g1/migration-rk3562/experiments/emmc-system/working-candidate.json`.
- eMMC sul retro (38;9), 15 bypass CPU non instradati riposizionati. Geometria
  verificata, non qualifica PI. Dieci condensatori storage + R8005 a massa:
  percorsi 0,72–1,34 mm, 36 primitive aggiunte. Tutti i collegamenti precedenti
  preservati; DRC individuale senza nuove violazioni. NOR rimossa nel derivato.
- `rebuild_emmc_pcb.py` ricostruito e passato; rollback in caso di errore.
  Le vecchie ricerche locali fallite e i ritorni lunghi non sono più checkpoint.
- Inventario aggiornato: 285 reti totali, 278 multi-pad, 240 ancora aperte;
  aumento rispetto a 231 dovuto alle nuove reti storage, non perdita dei vecchi collegamenti.
- JLC: evidenze aggiornate `emmc-system/system/review/bga-process-review.json`.
  0,09 mm standard non basta per attraversare il passo 0,5/land 0,25;
  3 mil con sovrapprezzo o processo via-in-pad da confermare. Non qualificato.
- Nessun ordine, commit o push. Le sezioni sotto sono storico.

## Hardware — 14 novembre 2026, dopo il commit 3a29334

- PCB principale invariato: `stacked-expansion/working-candidate.json`, SHA
  `151a54c68218efe8a5a531532cc1dfe28d964d757d3ab40b78c80718e2ba3bbc`.
- eMMC nello schema: R8006/R8007 collegano i rail candidati; 1.996 disposizioni
  controllate, 18 componenti con MPN/JLC e footprint. Fonti JLC del 13–14 novembre;
  subtotale indicativo del solo storage 17,8101 USD, non preventivo PCBA.
- eMMC PCB separato: `emmc-system/pcb`. La migrazione conserva tutte le 4.051
  piste/via del checkpoint e verifica 1.816 pad esistenti più 187 nuovi.
  **Piazzamenti emmc-placement ed emmc-repacked respinti dal DRC**, non promuovere.
  La ricerca successiva è descritta da `emmc-placement-search.json`: non prova
  che ogni piazzamento sia impossibile. Serve ripianificare la zona storage e
  i bypass tenendo conto del rame USB/DDR. Nessuna produzione o boot verificati.
- Espansione ruotata 180°, stesso pinout: pipeline completa fino a logic-reference
  riprodotta. Variante `aux-io-miso-hop`: sei segnali ausiliari collegati.
  Variante `aux-io-constrained-first`: sette, inclusa I2C completa, ma senza
  clock/MOSI SPI e CS0. Nessuna variante è un superset del checkpoint principale;
  restano studi separati. Audit di continuità e DRC per identità degli oggetti.
- Audit più rigorosi: oltre ai conteggi, confronto UUID/tipo/severità delle
  violazioni e assert sulle sei connessioni funzionali del blocco espansione.
- Test router raggiungibilità e regressione DRC: tre casi ciascuno passati.
- RK3562 / 1 GB LPDDR4; PCB ancora 90×40 mm, target 85×35 non convalidato.
  Inventario principale: 231 reti multi-pad ancora aperte. Non vicino al rilascio.
- Nessun acquisto, commit o push eseguito in questa sessione.

## Hardware — checkpoint corrente 13 novembre, espansione ed eMMC

- Routing: leggere `hardware/phoenix-g1/migration-rk3562/experiments/stacked-expansion/working-candidate.json`; ora aux-io, quattro segnali aggiuntivi verificati, sette ancora aperti. DRC139 invariato, 2460 primitive originali preservate, cinque riserve meccaniche. No USB qualificata o fori finalizzati.
- Flash: candidato completo `experiments/emmc-system`, 43 fogli, 1992 assegnazioni verificate. Vecchia NOR eliminata solo nello schema candidato; VCCIO2 a rail1V8 dedicato ancora senza sorgente qualificata. R8005 STRB47k aggiunta da datasheet. PCB non migrato.
- Rigenerazione e audit eMMC: `hardware/phoenix-g1/tools/rebuild_emmc_system.py` con Python sexpdata. I report del candidato, non quelli copiati storicamente, fanno fede.
- Inventario completo `stacked-expansion/pcb/connectivity-inventory.json`: 276 reti, 269 con più pad, 231 ancora con gruppi separati. È una verifica di connettività e non di SI; il routing complessivo non è prossimo alla chiusura.
- Non ordinare: PMIC/rail, sequenza/boot, layout eMMC, fanout J3, USB/DDR/SI, conflitti meccanici e formato85x35 restano da chiudere. Nessun commit/push in questo turno.

## Checkpoint corrente con fissaggi protetti

`stacked-expansion/working-candidate.json` aggiornato: logic-reference rigenerato
con cinque rule area meccaniche su tutti gli strati. Tutti i controlli feed,
J3, masse, GPIO SoC e 3V3 passano. DRC invariato; 1044 segmenti/via aggiunti.
R8103 ora (82.5,9.5)/0°, C8103 (79,4.2)/180°; usare sempre JSON attuali.
`rebuild_stacked_expansion.py` riproduce e verifica la catena, senza acquisti.
Aux-io è un esperimento separato in corso, non il checkpoint fino ad audit.

## Espansione: alimentazione e controlli completati geometricamente

`stacked-expansion/working-candidate.json` punta ora a `pcb/logic-reference.kicad_pcb`.
Audit logic-reference: input/output eFuse, 14 masse J3, due GPIO dal SoC e
riferimento 3V3 tutti continui; DRC invariato, 747 nuovi segmenti/via.
R8102 orientata 180°. Budget potenza/termica/USB e fissaggi NON qualificati.
Routing ausiliario UART/I2C/SPI in lavorazione nel derivato aux-io: non usarlo
senza leggere audit/risultato finale. Nessun commit/push richiesto in questa fase.

## Checkpoint espansione aggiornato — 13 novembre 2026

Usare `hardware/phoenix-g1/migration-rk3562/experiments/stacked-expansion/working-candidate.json`:
`pcb/fault-supply.kicad_pcb`, audit dedicato. Quattro reti locali, sette ritorni
GND, condensatori IN/OUT e pull-up fault collegati; nessun nuovo errore DRC.
114 nuovi segmenti/via, originali preservati. NON completo: feed ingresso,
uscita J3, GPIO SoC, USB, qualifica energetica/termica e fissaggi restano aperti.
Il riferimento GND verificato è U4.69; altri GND PMIC già scollegati.
Il browser host è indisponibile per il calcolatore JLC; niente impedenze inventate.
Le note più vecchie sotto sono storiche e possono riferirsi a derivati superati.

## Collegamenti protezione espansione

Nuovo derivato `stacked-expansion/pcb/control-routed.kicad_pcb`: due reti locali
ILIM/dVdt collegate e verificate; leggere control-routed.json per i limiti.
Non promosso: dVdt lungo, GPIO/massa/potenza/USB ancora incompleti.
Tentativo mount-clearance-trial SCARTATO, non ripartire da quel PCB.

## Riserve hardware aggiuntive

Overlay meccanico aggiornato: H8101/H8102 per scheda figlia più H8103–H8105
per staffe/case/dissipazione. `mounting-interface.json` separa `mounts` e
`auxiliary_mounts`; i render della figlia usano solo `mounts`.
Nessun foro reale e nessuna pista modificati; liberare componenti prima della
foratura, soprattutto clock presso H8104. Passivo rimane la scelta prioritaria.

## Fissaggi espansione — requisito da non perdere

Riservati H8101/H8102 M2 nell'overlay CAD `hardware/phoenix-g1/migration-rk3562/experiments/stacked-expansion/mechanical/mounting-reservations.kicad_pcb`.
Leggere `mounting-interface.json`: sette componenti da spostare, fori non ancora realizzati.
Blocca rilascio e definizione scheda figlia finché ingombri e distanziali non sono qualificati.

## Hardware — sostituzione J3, 13 novembre 2026

Candidato in `hardware/phoenix-g1/migration-rk3562/experiments/stacked-expansion/`.
Leggere README e audit.json: Hirose DF40 40 poli vicino Ethernet, SOSTITUISCE 2×10.
Schema e piazzamento controllati; USB host e alimentazione nuove NON instradate.
Il checkpoint LPDDR4 resta invariato. Non confondere candidato con produzione pronta.
Target 85×35; candidato ancora 90×40. eMMC resta nel candidato separato.

## ROCK — deployment fisico 2026-11-12

Phoenix 0.1.0-rock1 installato su b60 Debian 11. 69 test passati, HTTPS/AP/DHCP,
aggiornamento firmato reale e reboot verificati. Forwarding Ethernet e blocco
provati con client virtuale; USB fisica e account NordVPN non verificati.
Vedere platforms/linux/boards/rock4c-plus/BRINGUP.md. AF_PACKET worker approvato
esplicitamente. Credenziali SSH invariate, nessuna nuova chiave installata.
Non presumere IP o tunnel ancora attivi; riscoprire target prima di modificare.

## Obiettivo meccanico hardware — 2026-11-12

Scelta esplicita dell'utente: puntare a **PCB 85 × 35 mm**. Decisione salvata in
`hardware/phoenix-g1/mechanical/pcb-envelope-target.json`. Non confondere con
dimensioni del case o con fit verificato. Conservare il checkpoint 90 × 40 mm;
90 × 30 mm non è dimostrato impossibile, ma resta alternativa più vincolante,
non il target selezionato. Prima di rifare il routing verificare piazzamento
completo includendo eMMC saldata, display/comando, espansione e termica passiva.
LTE/eSIM rinviati; predisposizione espansione da progettare. Nessuna modifica
del PCB originale è stata eseguita nello screening di ingombro.

## Checkpoint revisione e endurance — 2026-11-11

Utente: procedere senza account NordVPN reale (scelta esplicita). Non chiedere
nuovamente il token per questa tranche. Nessuna scheda disponibile.
68 test Python, 605 secondi/102 cicli Docker con controllore persistente (RSS
22144 KiB stabile, FD 4), cinque update VM più rollback/reboot, UI Chromium /
WebKit / Firefox e build ESP32 passati. Vedere SECURITY_REVIEW.md e VALIDATION.md
in platforms/linux. Correzioni: perdita tunnel confermato senza grace iniziale,
JSON rigoroso RPC, deadline lettura, header duplicati/CSP, spazio update, logout
mobile e pulizia campi sensibili. Container di test rimossi. CI predisposta,
non pubblicata/eseguita su GitHub; niente commit/push in questa sessione.

## Checkpoint Linux — autonomia senza hardware, 2026-11-11

Completati DNS/HTTPS NordVPN sull’uplink selezionato, frontend HTTPS non root,
worker RPC con SO_PEERCRED, VM QEMU con systemd reale e reboot/rollback,
fault injection, contratti UI e workflow CI. Leggere platforms/linux/VALIDATION.md.
63 test Python, traffico Linux, VM, core C/JS e build ESP32 passati. Catalogo
pubblico NordVPN reale verificato senza token. Nessuna prova ROCK o account VPN.
Deployment ora usa quattro unità, HTTPS 8443 e LoadCredential; il vecchio HTTP
8085 è solo CLI sviluppo. Vecchi checkpoint sotto sono storico, non stato attuale.
La ROCK non è con l’utente. Nessuna richiesta di commit/push in questa sessione.

## Checkpoint Linux — completamento offline 2026-11-11

La ROCK non è disponibile con l’utente. Non chiedere nuovamente IP o accesso
finché non comunica che è tornata disponibile. Il backend, AP/STA opt-in,
aggiornamenti applicativi firmati e installer sono in platforms/linux.
Leggere README, API_STATUS, VALIDATION e deploy/UPDATES per capacità e limiti.
Non confondere i vecchi blocchi storici "non implementato" con lo stato corrente.
USB gadget/driver, radio, NordVPN reale, ciclo systemd/power loss e prestazioni
rimangono da verificare sul target. Il control plane mantiene route di gestione.
Nessun commit/push in questa sessione; non eseguirli senza richiesta.

# Migrazione offline: lifecycle, hotspot e pacchetto — 2026-11-11

Utente conferma di NON avere con sé la ROCK. Non cercare di flashare o presumere
Linux avviato. Backend esteso: rifiuto richieste invalide prima di mutazioni,
errori diagnostici senza drop VPN, shutdown ordinato e stop guard systemd,
hotspot opt-in con controllo ownership e rollback, bundle allowlisted con hash.
41 test su Debian + suite kernel/traffico + dnsmasq e sintassi systemd passati.
Leggere platforms/linux/VALIDATION.md e deploy/README.md. AP reale/USB/NordVPN
restano da provare. STA/uplink Wi-Fi e OTA Linux restano non implementati;
non dichiarare migrazione completa. Nessun commit/push richiesto.

---

# Backend Linux implementato, prove virtuali — 2026-11-11

Leggere platforms/linux/README.md, API_STATUS.md, VALIDATION.md e deploy/README.md.
API/servizio loopback, nftables, WireGuard kernel, adapter NordVPN, rotazione,
storico, vault privato e persistenza revisionata implementati. Test unitari/HTTP
su host e Debian; test reali in Docker di NAT, deny, forwarding/source filter,
tunnel WG con handshake e blocco dopo rimozione tunnel. Build ESP32 riuscita.
UI unica con capabilities; funzioni Wi-Fi non disponibili disabilitate.
ROCK non ancora avviata: provisioning Wi-Fi/USB, NordVPN reale, systemd,
DNS/IPv6/endurance e performance devono essere verificati sul banco.
Nessun commit/push di questo lavoro ancora richiesto. Nessuna chiave nei file
versionati. Docker Desktop avviato per test; container/reti di prova rimossi.

---

# Port Linux avviato — 2026-11-11

Scelta banco: immagine ufficiale Radxa ROCK 4C+ Debian 12 Bookworm KDE R2,
poi uso headless; fonti e istruzioni in platforms/linux/boards/rock4c-plus/README.md.
Implementati inventario read-only e storage SQLite transazionale della
configurazione desiderata non segreta. 5 test host passati con tools/test-linux.sh.
Non ancora implementati API, applicazione firewall/VPN e provisioning rete;
nessuna prova fisica, nessun sistema scritto su microSD. Prossimo lavoro:
validazione policy compatibile ESP32, API e separazione privilegi di rete.

---

# Repository multi-piattaforma — 2026-11-11

Sorgenti ESP32 spostati in platforms/esp32/main; UI in shared/web;
core portabile in shared/phoenix_core. Root ancora entrypoint ESP-IDF.
Leggere AGENTS.md e docs/PROJECT_STRUCTURE.md per riprendere il lavoro.
Linux è solo predisposto: piano in platforms/linux/README.md, nessun backend
operativo. ROCK 4C+ arrivata, collegata USB-C al Mac; supporto di avvio Linux
non ancora preparato. Non presumere accesso SSH o rete USB disponibile.
Lo storage della scheda custom è da chiudere: U18 SPI NOR 32 MB presente,
eMMC candidata ma non integrata nel PCB. Non confondere con la RAM LPDDR4.

---

# Filtro paesi NordVPN — 2026-11-06

Aggiunta opzione exclude_restricted, preset Phoenix da tabella NordVPN
https://nordvpn.com/blog/are-vpns-legal/ verificata oggi. NON classificazione di
server pericolosi. Elenco: CN RU BY TR IQ AE OM IN IR EG TM KP UG MM SA VE.
Filtro su pool casuale e scelte fisse, nessun fallback geografico. UI mostra
lista, fonte e data; flag in NVS schema2 con migrazione1 che preserva credenziali.
Abilitato sulla configurazione utente, rotazione casuale 300s invariata.
La cronologia Git resta invariata per istruzione esplicita dell’utente.
Il filtro viene pubblicato dopo 62efe05, con autore alpacx.

---

# Storico e navigazione VPN — 2026-11-06

UI: singola voce VPN, schede NordVPN e VPN WireGuard, spiegazione VPN/profilo.
Countdown locale a un secondo sincronizzato con API, sospeso se dati obsoleti.
Storico NordVPN 8 ore nel journal vpn_history (0xc20000, 128 KiB), 1344 record
CRC; API autenticata paginata vpn/history. Registrazione solo al primo handshake
riuscito di ogni connessione. Nessuna retrodatazione o cronologia inventata.
Test: tools/test-history.sh e node tests/test_countdown.cjs.
Token admin locale: results/gatewaybench/admin-token.txt; NON stampare.
Bridge 127.0.0.1:8085 lo inserisce automaticamente; altro token è NordVPN.
Verifica reale: API storico persistent=true con cinque connessioni conservate
dopo flash/riavvio. UI Chrome controllata: menu VPN, schede, spiegazione,
storico e countdown visibili; accesso locale automatico riuscito.
Seriale: aggiunto fflush(stdout) alle risposte PHADMIN per evitare timeout da
buffering. Bridge usa DTR/RTS true e separatore iniziale di comando.

---

# Pannello amministrativo e NordVPN diretto — 2026-11-06

Il gateway usa ora NordVPN direttamente, con chiave fornita dall’utente nel pannello.
Il Mac non è più un relay necessario. UI: http://127.0.0.1:8085 tramite
`tools/admin_bridge.py`, UART /dev/cu.usbmodem5B901859211, token locale in
results/gatewaybench/admin-token.txt (non stampare). Dall’AP: http://192.168.9.1.
Non aprire la seriale mentre il bridge la possiede. Arrestarlo prima del flash.
Build corrente: build-admin, conserva NVS durante aggiornamenti.

Implementati UI responsive, firewall ordinato, port forwarding, revisioni anti
conflitto, WireGuard persistente, provisioning NordVPN HTTPS e scheduler.
L’interfaccia non menziona il modello hardware. Paese vuoto: rotazione casuale
escludendo il precedente; paese selezionato: vincolo stretto. La rotazione era
spenta nella configurazione utente; viene abilitata a 300 secondi dopo i test.
Test host e API policy passati; regole temporanee ripristinate. Log rotazione reale:
results/gatewaybench/rotation-live.log. Vedere docs/API.md e docs/NORDVPN-P4.md.
Verifica HTTPS pubblica attraverso il tunnel riuscita: IP 186.247.43.8,
server NordVPN North Macedonia #13; Cloudflare riporta loc=BG (geolocalizzazione
distinta dal paese di catalogo NordVPN). Rotazione reale: Italy #536 → #476
restando in IT; poi Lebanon #3 → Uzbekistan #3 in modalità casuale. Stato precedente qui sotto è storico.

---

# NordVPN sul Mac — 2026-11-06

Utente ha attivato NordVPN sul Mac e segnalato IP telefono differente.
Verifica read-only: route 1.1.1.1 su utun6 (10.5.0.2), HTTPS IPv4 nuovo con
routing default e con --interface utun6 dà lo stesso IP pubblico 187.13.23.86.
Relay riavviato per eliminare sessioni TCP/UDP preesistenti; causa originaria
NON ancora isolata (possibili connessioni/cache, non dichiararla certa).
Nuovo handshake P4 riuscito, relay TCP/UDP ripreso senza errori iniziali,
P4 vpn=1 direct=0. Log nuovi server-nordvpn.jsonl e host-nordvpn.log in
results/gatewaybench. Stesso comando host-internet; nessun cambio route/DNS/pf
né configurazione NordVPN. Conferma esplicita utente ricevuta dopo riavvio relay: anche il telefono
mostra187.13.23.86, uguale al Mac/NordVPN.
Il relay usa routing Mac corrente, NON è vincolato a utun6. Il firewall P4
protegge il tratto fino al peerMac, non impone la presenza del secondo tunnel
NordVPN. Non promettere fail-closed rispetto a NordVPN senza implementazione.

---
# Prova integrata completata e Internet attivo — 2026-11-06

STATO FINALE: build-gatewaybench, Wi-Fi Phoenix-Test 192.168.9.1/24, P4 Ethernet
192.168.8.170, WireGuard 10.77.0.2 verso Mac192.168.8.103:51821. direct=false,
vpn=true. USB dati off. Nessuna modifica route/DNS/pf Mac, nessun flash C6/eFuse.

Internet dal telefono confermato dall'utente (ricerca Google). Exit userspace Mac
TCP/UDP pubblico IPv4 con DNS, TLS end-to-end. Mac e processo devono restare accesi;
IP pubblico della rete Mac, non di un provider remoto. Limiti relay: 256 sessioni,
TCP max10min, UDP idle30s; niente ICMP relay/IPv6/destinazioni private. Nessun log
di siti o query DNS. Firmware e chiavi di banco non sono un rilascio produzione.

Endurance terminata: 608.835 s, 45 cicli, 90 trasferimenti
completi da8MiB =720MiB (360 per direzione). Download 12.25 Mbit/s
(range 6.55–14.61), upload 22.33
(range 16.65–24.92). Nessun endurance_error,
nessun panic/reset durante prova. Heap campionato finestra prova 330444–397036 byte,
finale393452: nessuna deriva evidente, NON prova assoluta di assenza memory leak.

Confronto diretto stesso telefono/HTTP8MiB: 8.87download/22.89upload, sei completi.
TCP macOS nel diretto vs gVisor nel tunnel; non isolare costo crypto da questi dati.
Recupero peer dopo15s e nuovi trasferimenti già verificati nelle serie precedenti.

Egress mirato passato con controllo positivo e ACKprobe: tre UDPclient sintetici
porte53/443/8081 versoMac, zero plaintext VPN/blocked, tre direct, zero blocked.
NON audit completo DNS/IPv6 né cattura di tuttaEthernet. Tentativi inconcludenti
conservati; generatore corretto PBUF_LINK. check_egress.py ora forza/attende modalità
VPN anche all'avvio per rendere ripetibile il test quando stato iniziale diverso;
non rieseguirlo durante navigazione/trasferimenti perché cambia modalità.

Catture tcpdump terminate al termine della prova; server Internet e monitor UART restano attivi.

Log finali results/gatewaybench/server-final-exit.jsonl, uart-probe-fixed.log,
host-final-exit.log, endurance-summary.json, egress-results.json e catture locali.
Host attivo .tools/wgbench/host-internet -gateway-server -internet-exit
-direct-listen192.168.8.103:8080 -dir results/gatewaybench. Listener diretto ristretto
alla P4, pagina non raggiungibile tramite VPN (destinazioni private bloccate).
Pagina VPN http://10.77.0.1:8080; navigazione normale daPhoenix-Test con dati mobili
spenti. Monitor UART di banco limitato3600s: non aprirne un altro (può resettareP4).
PasswordAP in results/gatewaybench/wifi-password.txt; mai stampare chiavi private.

Codice e risultati documentati in benchmarks/gateway/README.md. Build firmware,
flash verificata, test esistenti e test Go policy/DNS+HTTPS passati. Nessun nuovo
commit/push. Resta warning compatibilità esp-hosted C6; versione C6 non aggiornata.

---

## Confronto diretto completato — 2026-11-06

3 x 8 MiB/direzione completati senza VPN: download telefono 8.87 Mbit/s
(intervallo 6.73–11.27), upload 22.89 Mbit/s (19.92–26.95).
Server-final-exit.jsonl remote=192.168.8.170 conferma percorso diretto/NAPT.
VPN ripristinata via UART subito dopo; non lasciare direct attivo.
Prestazioni senza VPN non molto superiori alle serie con VPN: non attribuire
il limite alla sola crypto; Wi-Fi/SDIO/rete e TCP host diverso sono confondenti.
Invitato utente ad aprire 10.77.0.1:8080 e avviare Prova prolungata 10 minuti.
In attesa risultati endurance_complete o endurance_error nel log corrente.

---
# Internet e verifica uscita — 2026-11-06

Internet attivato attraverso il Mac con relay userspace TCP/UDP pubblico IPv4,
trasparente per il telefono: AP → firewall/NAPT → WG → Mac sockets → Internet.
Utente conferma ricerca Google riuscita con dati mobili spenti. Nessuna route/DNS
Mac o pf modificati. Non è un servizio VPN esterno: IP pubblico della rete Mac;
Mac/peer devono restare attivi. TCP/UDP supportati, non ICMP forwarding o IPv6.
Relay limita 256 sessioni, TCP a 10 min, UDP idle 30 s; destinazioni private,
loopback, link-local e riservate escluse. Non registra destinazioni di navigazione.
Test automatico: DNS UDP e HTTPS con certificato valido a example.com passati.
Netstack locale derivato dalla versione wireguard-go bloccata, licenza preservata;
HandleLocal=false necessario con NIC promiscuo. File exit.go e test dedicati.

Firmware corrente build-gatewaybench include bench UART commands (solo flag di
banco) e probe IP sintetico; admin HTTP/pairing disattivati nel bench. Produzione
non abilita questi comandi. `bench direct` ripristina VPN automaticamente dopo
300 s; `bench vpn`, `bench blocked`, `bench probe`. Monitor seriale unico legge
comandi da results/gatewaybench/uart-command.txt. Scrivere atomicamente una riga
con nonce univoco e comando. Non aprire un secondo monitor (reset possibile).

Test egress con ACK di completamento probe passato, egress-results.json:
3 UDP sintetici da AP 192.168.9.250 verso Mac, porte 53/443/8081, ID 64000..64002.
0 in chiaro con VPN, 0 blocked, tutti 3 direct (controllo positivo), 0 blocked.
Cattura egress-wide.pcap. Limitato a pacchetti sintetici e percorso verso Mac;
NON prova generale di assenza DNS/IPv6 leak o cattura di tutta l'uscita Ethernet.
Tentativi precedenti inconcludenti conservati: generatore senza headroom Ethernet;
corretto allocando PBUF_LINK. Ultima serie verifica ACK UART per ogni probe.

Processi attivi: host-internet con -gateway-server -internet-exit
-direct-listen 192.168.8.103:8080 -dir results/gatewaybench; listener diretto accetta
solo sorgente P4 192.168.8.170. Server nel tunnel 10.77.0.1:8080.
Monitor benchmarks/gateway/monitor_control.py limitato a 3600 s.
Log correnti uart-probe-fixed.log, server-final-exit.jsonl, host-final-exit.log.
Due catture Mac attive mac-p4.pcap e egress-wide.pcap. Nessun commit/push nuovo.

Confronto diretto appena avviato (autoscadenza 5 min), utente invitato ad aprire
http://192.168.8.103:8080 da Phoenix-Test e premere Misura. Raccogliere i 6 risultati,
poi ripristinare bench vpn, verificare handshake e invitare a 10.77.0.1:8080:
pulsante nuovo «Prova prolungata: 10 minuti (traffico locale)». Non dichiarare
completati confronto/endurance prima dei risultati. Il confronto usa stesso HTTP,
telefono e payload ma TCP Mac OS nel diretto vs gVisor nel tunnel: non isola crypto.

---

## Trasferimenti dopo recupero — 2026-11-06

Completati tutti i 6 trasferimenti da 8 MiB dopo interruzioni del peer, senza
riavvio della scheda. Media aggregata download 6.38 Mbit/s,
upload 16.84 Mbit/s. Intervalli download 4.13–9.55, upload
13.42–20.89 Mbit/s. Prima serie 12.43/23.03: recupero funzionale verificato,
prestazioni variabili e inferiori nella seconda serie; causa non isolata.
Nessun panic/reset osservato. Non dichiarare stabilità prestazionale né assenza
fughe dimostrate. Dati in server-v2.jsonl, ultimi sei browser_result di transfer.

---

## Recupero peer verificato — 2026-11-06 17:14

Ricevuti due resoconti completi peer_outage dal telefono in server-v2.jsonl.
Ultima prova: richieste OK a 0/0.722/1.471 s, fallite da 2.202 a 15.419 s,
nuovamente OK da 17.622 s fino a 34.817 s. Peer disattivato alle 17:13:28.468
e riattivato alle 17:13:43.471 (+15 s); nuovo handshake verificato.
Recupero automatico delle richieste HTTP nel tunnel confermato, senza riavvio
della scheda. Non è prova completa di assenza fughe né stress test; nuova serie
di throughput dopo outage ancora da eseguire.

---
# Prova gateway integrato avviata — 2026-11-06

Firmware corrente **build-gatewaybench**, layout Phoenix OTA con app 0x20000.
USB dati off, C6 AP Phoenix-Test 192.168.9.1/24, Ethernet 192.168.8.170,
WireGuard 10.77.0.2 verso Mac 192.168.8.103:51821. Firewall/NAPT/hook di
produzione attivi, direct=false. Non è ancora una prova completa superata.

Telefono disponibile; utente invitato a disabilitare dati mobili, collegarsi AP,
aprire http://10.77.0.1:8080. Password in results/gatewaybench/wifi-password.txt;
chiavi/header locali nella stessa cartella. Non esporre chiavi o pubblicare binari.
Mac serve pagina solo nel tunnel tramite .tools/wgbench/host -gateway-server
-dir results/gatewaybench, nessuna modifica route/DNS di sistema.

Correzioni questa sessione:
- subnet AP 192.168.8.0/24 collideva col router: passata a 192.168.9.0/24 in
  gateway, setup Wi-Fi, controllo overlap e documentazione.
- ph_canforward usava ip_current_input_netif(), che in IDF lwIP viene impostato
  solo DOPO il ramo forwarding per consegna locale: tutti i pacchetti AP erano
  ammessi al firewall ma non inoltrati. Ora ph_ip4_input registra n in p->if_idx
  e ph_canforward usa netif_get_by_index. Vale anche per ingressi WG decapsulati,
  senza ereditare il contesto Ethernet esterno. Primo tentativo conservato.

Build e test host passati, flash verificata, DHCP Ethernet/AP e handshake WG
verificati. Primo telefono DHCP 192.168.9.2. Dopo correzione/reflash percorso completo verificato: 3 x 8 MiB/direzione,
download telefono 12.43 Mbit/s, upload 23.03 Mbit/s aggregati. NAT source
10.77.0.2 visto sul Mac. Interruzione peer ancora pendente; non dichiarare
kill-switch/assenza leak completamente validati.
C6 host/slave version mismatch warning persiste; nessun flash C6 effettuato.

Log correnti: results/gatewaybench/uart-v2.log, server-v2.jsonl,
host-status-v2.log, mac-p4.pcap (cattura solo traffico visibile al Mac, NON tutta
la LAN), uplink-negative.json. Log primo tentativo senza -v2 conservati.
Processi lasciati per la prova: monitor UART limitato 1800 s, server WireGuard,
tcpdump su en0. Apertura UART può resettare P4: non riaprire durante misura.
Pagina offre 3 x 8 MiB/direzione e peer down 15 s, con risultati sul Mac.
Interruzione tunnel non equivale da sola a prova completa assenza leak.
Procedura: benchmarks/gateway/README.md. Nessun commit/push nuovo.

---
# Ultimo stato — WireGuard misurato sulla P4, 2026-11-06

Installato benchmarks/wireguard/build-dma: app factory a 0x10000, non gateway
Phoenix. P4 v3.1 MAC e8:f6:0a:e3:b3:6e, Ethernet 100 Mbit/s full-duplex,
LAN 192.168.8.170. Mac 192.168.8.103. USB device, Wi-Fi, NAT e firewall gateway
non esercitati. Nessun eFuse o route/DNS del Mac modificati.

Endpoint Mac temporaneo userspace wireguard-go + gVisor, processo terminato
al termine dei test. Binario/toolchain locali .tools/wgbench; chiavi di banco
in results/wgbench (0600, escluse da Git). Firmware contiene chiave di banco:
non pubblicare binari. Config firmware fissa endpoint e orologio del setup.

| Direzione | TCP senza VPN (baseline) | TCP nel tunnel WireGuard | Intervallo WireGuard |
|---|---:|---:|---:|
| Mac → P4 | 74.54 Mbit/s | 15.26 Mbit/s | 12.02–27.12 |
| P4 → Mac | 38.98 Mbit/s | 33.61 Mbit/s | 33.22–33.81 |

Sei trasferimenti completi da 32 MiB, handshake e contatori WG verificati.
Media aggregata = bit totali/tempo totale. Variabilità in RX ancora marcata;
non è uno stress test né misura di forwarding/USB. Confronto non isola solo
la crypto: cambiano stack TCP del Mac (gVisor) e buffer DMA del firmware.

Due problemi reali corretti:
1. ESP-IDF 5.5 interpretava netif->state di WG come esp_netif_t: crash DHCP
   durante netif_add. CONFIG_LWIP_PPP_SUPPORT=y separa client_data senza creare
   un link PPP; aggiunto a defaults e guardia compilazione in wireguardif.c.
   Le build Phoenix con sdkconfig vecchi richiedono tale opzione esplicita.
2. AllowedIPs RX verificava la destinazione invece della sorgente IPv4:
   corretto nel componente condiviso. Test positivo traffico e negativo con
   peer autenticato/source 10.77.0.3 non autorizzata: handshake OK, TCP respinto.

Prima dei buffer DMA aumentati: una coppia completa a 26.98/32.66 Mbit/s,
poi due upload incompleti a 120 s (27097844 e 30617644 byte, ~1.81/2.04 Mbit/s).
Con DMA 1536 byte, RX=30, TX=10, TCP WND/SND=63360: serie finale completa.
Non nascondere questi fallimenti né dichiarare risolta la stabilità generale.

Log finali: results/wgbench/client-dma.jsonl, uart-dma.log,
host-dma-status.log, source-rejection-dma.log. Prove precedenti conservate.
Build benchmark e test host esistenti (firewall/parser/USB sync) passati.
Procedura e limiti: benchmarks/wireguard/README.md.

---
Registro precedente (storico):

# Confronto TCP completato — 2026-11-06

Firmware corrente benchmarks/ethernet/build-tuned, finestra/buffer 63360 byte,
mailbox TCP 46 / tcpip 64. Link 100 Mbit/s full-duplex, P4 192.168.8.170.
Sei trasferimenti da 32 MiB completi; throughput aggregato (byte totali/tempo):

| Direzione | Default Mbit/s | Buffer aumentati Mbit/s | Miglioramento |
|---|---:|---:|---:|
| Mac → P4 | 14.27 | 74.54 | 5.22× |
| P4 → Mac | 8.91 | 38.98 | 4.38× |

Intervalli tuned: U 63.61–82.49, D 34.11–42.55 Mbit/s. Config precedente:
WND/SND_BUF 5760, mailbox 6/32. Stessi sorgenti/CPU 400 MHz/protocollo/rete.
Log results/ethernet-tuned-client.jsonl e results/ethernet-tuned-uart.log.
Forte miglioramento osservato, ma rete condivisa e variazioni impediscono di
attribuire ogni differenza ai buffer. Nessuna VPN, USB o forwarding misurati.
Heap campionato dopo trasferimenti: minimo 479800 byte; non è minimo globale
né prova di assenza leak. Firmware di banco TCP 5001 ancora installato.
Prossima prova utile: WireGuard end-to-end con peer locale e percorso client
realizzabile (USB ancora subordinata alla fixture). Non confondere microbenchmark
crypto ~49.6 Mbit/s con throughput tunnel, né prevedere prestazioni S31.

---
# Ultimo esito — baseline TCP completata, 2026-11-06

Seriale tornata disponibile; DHCP P4 192.168.8.170, Mac 192.168.8.103.
Primo tentativo interrotto da riavvio osservato durante apertura monitor seriale;
ripetuto dopo DHCP, senza ulteriori aperture seriali. Sei trasferimenti completati
(3 x 32 MiB per direzione) con conteggi completi:
Mac -> P4: 14.27 Mbit/s aggregati, intervallo 13.94–14.68.
P4 -> Mac: 8.91 Mbit/s aggregati, intervallo 8.47–9.17.
Ping durante trasferimento: 4/4 risposte, media 2.632 ms (campione breve).
Log client: results/ethernet-retry2-client.jsonl; boot: results/ethernet-retry-uart.log.
Rete senza VPN/firewall/USB, TCP default (WND/SND_BUF 5760, MSS 1440).
Misure includono LAN e collegamento Mac; non rappresentano limite del PHY/CPU.
Firmware corrente: benchmarks/ethernet, server TCP 5001 solo per LAN fidata.
Prossimo passo: confronto controllato con buffer TCP ottimizzati, poi VPN.

---
# Aggiornamento rete — 2026-11-06

Mac passato a 192.168.8.103/24. ARP di 192.168.8.170 corrisponde alla P4
(e8:f6:0a:e3:b3:6e), ma connessione TCP 5001 scade ancora (10 s).
Porta /dev/cu.usbmodem5B901859211 non più presente, nessuna USB seriale
alternativa rilevata. Occorre ricollegare USB-C dati/alimentazione al Mac per
leggere DHCP e stato firmware. Nessuna nuova misura throughput disponibile.
Il tentativo di acquisizione UART ha troncato results/ethernet-benchmark-uart.log;
il precedente esito link/DHCP rimane documentato qui e nel README benchmark.

---
# Stato attuale — baseline Ethernet, 2026-11-06

Dopo il collegamento Ethernet richiesto dall’utente, installato firmware autonomo
benchmarks/ethernet (sostituisce il benchmark crypto). Flash verificata, P4 v3.1
MAC e8:f6:0a:e3:b3:6e. Link IP101 100 Mbit/s full-duplex verificato; DHCP
192.168.8.170/24, gateway 192.168.8.1. Server TCP di banco sulla porta 5001.
USB dati/Wi-Fi/VPN non attivi, nessun eFuse o route Mac modificati.
Mac en0 192.168.1.179/24 via 192.168.1.1. Connessione TCP alla P4 scaduta dopo
10 s: nessuna misura throughput rete disponibile. Portare Mac e P4 sulla stessa
LAN, poi rieseguire benchmarks/ethernet/client.py con IP verificato su UART.
Log: results/ethernet-benchmark-uart.log. Firmware di test non autenticato:
solo LAN fidata. App factory 0x10000; non usare offset OTA del gateway.

---
Registro precedente (storico):

# Stato attuale — benchmark Waveshare, 2026-11-06

L’utente ha autorizzato nuove prove sulla Waveshare dopo l’erase.
Installato un firmware autonomo di benchmark crypto dalla directory
benchmarks/crypto, NON il gateway Phoenix. P4 v3.1 confermata via MAC
(e8:f6:0a:e3:b3:6e). Flash bootloader/partizioni/app verificata da esptool.
USB dati, Ethernet e Wi-Fi non inizializzati; eFuse non modificati.
Ethernet non collegata, come confermato dall’utente.

P4 400 MHz, build -O2, task singolo CPU0, ChaCha20-Poly1305 della libreria
WireGuard presente nel repository, buffer interni. Tre prove da 1000 pacchetti
per dimensione. Con payload 1424 byte: encrypt 49.62–49.63 Mbit/s, decrypt
49.70–49.72 Mbit/s. Con 512 byte: 46.54–46.57 / 46.67–46.70; con 64 byte:
24.51–24.80 / 25.02–25.19. Roundtrip e tag alterato verificati.
Tempi delle sole chiamate crypto: escluse pause, confronto dati, rete e VPN.
Non sono throughput end-to-end né limiti assoluti del silicio o stime S31.
Log locale: results/crypto-benchmark.log. Procedura: benchmarks/crypto/README.md.
Per prove rete serve collegare Ethernet; USB richiede ancora fixture verificata.
Il gateway precedente resta nel repository; NON usare i suoi offset app per
questo benchmark (partizione factory a 0x10000, layout diverso).

---
Registro precedente (storico):

# Stato attuale — cancellazione richiesta dall’utente, 2026-11-06

La flash del P4 è stata cancellata su richiesta dell’utente. Non ricaricare
firmware né riprendere automaticamente lo sviluppo: serve una nuova istruzione.
Le istruzioni e i risultati sottostanti descrivono lo stato precedente all’erase.
Il repository e il backup sul Mac restano conservati. Il C6 è un chip distinto;
la sua flash non è stata cancellata tramite la porta seriale del P4.

# Ripresa

1. Leggere README, PROGRESS, TASKS, docs/HARDWARE.md e docs/OTA.md. Touch escluso.
2. SDK bloccato: ~/esp/esp-idf commit 10ca0dff2f40aeb539f22d1ef88d031cf7421743.
   Python: ~/.espressif/python_env/idf5.5_py3.9_env/bin/python.
3. Scheda identificata ESP32-P4 v3.1, porta /dev/cu.usbmodem5B901859211,
   CH343 1A86:55D3 seriale 5B90185921. Backup originale completo già verificato:
   results/recovery/original-flash.bin, hash in PROGRESS. Non leggerne il contenuto
   nei log. Non concorrere su seriale con altri monitor/flash.
4. Non caricare build/ o build-lab/: sono per silicio precedente.
   Firmware di banco USB off: build-signed. Include scan C6 al boot e firma software.
   Chiave riservata esistente results/signing/development.pem: NON rigenerarla,
   NON stamparla. Token attivo results/admin-uart.token: NON stamparlo.
5. Build e test:
   ./tools/test.sh
   ./tools/build.sh -B build-signed -D SDKCONFIG=build-signed/sdkconfig -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.rev3;sdkconfig.c6probe;sdkconfig.signed'
   python tools/test_signatures.py build-signed/phoenix.bin results/signing/development.pem
   Usare il Python IDF per espsecure/serial. Build richiede ambiente locale fuori
   sandbox per component manager/sysctl. Non cambiare globalmente SDK o rete Mac.
6. Prima di flash verificare CONFIG_SECURE_BOOT e CONFIG_SECURE_FLASH_ENC_ENABLED
   disattivati, revision min 300 e USB off. Per aggiornare solo app attuale ota_0:
   python -m esptool --chip esp32p4 --port /dev/cu.usbmodem5B901859211 --baud 460800 --after no_reset write_flash 0x20000 build-signed/phoenix.bin
   python tools/monitor.py --port /dev/cu.usbmodem5B901859211 --reset --seconds 45
   Dopo una futura OTA controllare slot attivo prima di riutilizzare questo indirizzo.
7. USB compilata separatamente in build-usb-rev3, NON flash finché fixture/power
   non siano verificati. USB-C è programmazione; Type-A OTG sorgente VBUS.
   Era stata chiesta descrizione dei cavi Ethernet/alimentazione/USB: controllare
   eventuale risposta utente prima di richiedere nuovamente queste informazioni.
8. C6 scan passa; warning versione slave 0.0.0 non equivale a incompatibilità
   delle API base. Non aggiornare C6 alla cieca. STA/AP/client ancora da provare.
9. Ultimo boot verificato: results/boot-final.log (firma RSA-PSS, pairing, scan
   13 reti); immagine/hash in results/firmware-final.json. Priorità: link/DHCP Ethernet con
   cavo confermato; fixture USB, enumerazione Mac/DHCP e percorso NAT; solo dopo
   prova VPN con profilo fornito o endpoint locale di test. Nessuna modifica
   automatica delle route del Mac. Test leak/OTA indicati nei documenti.
10. Continuare implementazione IP statico, profili/regole configurabili e
    robustezza. Non dichiarare terminato il prodotto o provati NAT/VPN dalla build.

### Vincolo NordVPN aggiunto dall'utente (2026-11-06)
NordVPN DEVE terminare direttamente sul P4; niente relay Mac. Paese selezionato: restare sempre in quel paese; nessuna selezione: rotazione casuale dei paesi/server. Aggiunti `vpn_rotation.[ch]`, test host passati (100000 selezioni) e `docs/NORDVPN-P4.md`. Questo è solo il selettore, non un'integrazione completa né già flashata. Continuare il task interfaccia amministrativa/firewall/port forwarding/VPN e account NordVPN autonomamente. Non dichiarare completato. Tutte le modifiche precedenti sono ancora presenti e non committate.

### Aggiornamento pannello speedtest nativo (2026-11-12)
ROCK aggiornata a release firmata 0.1.0-rock3 / seq3 / 3-a1d0ac24fe38d8ba.
Nuovo download HTTPS curl nativo Serverius DC3, quattro flussi 10s, solo download;
UI dati ricevuti/durata, niente stime upload/ping. 74 test passati su ROCK,
browser desktop/mobile passato. Misura live VPN Italy #534: 322,31 Mbps,
59,4 °C. Paese fisso IT, VPN connessa al termine. Dettagli BRINGUP/API_STATUS.
Non presumere IP o stato VPN invariati alla prossima sessione. Nessun commit.

### Ripresa hardware — eMMC (2026-11-13)
Utente senza scheda: lavoro CAD, nessun accesso/modifica alla ROCK. Checkpoint
LPDDR4 `working-board.json` immutato (wifi-relocation/io.kicad_pcb, 90×40 mm).
Nuovo esperimento `hardware/phoenix-g1/migration-rk3562/experiments/emmc-8gb/`:
foglio eMMC 8GB + supporti candidati, footprint153pad, mappa11segnali RK3562,
audit179disposizioni superato, ERC12 segnalazioni isolate non soppresse.
NON integrato nel sistema/PCB: sostituire NOR su pin FSPI condivisi, rivedere
VCCIO2 U1.1F14 da3V3 a1V8, qualificare boot/reset/power e loader. Non VCCIO1.
JLC C499918 pubblico aggiornato: initialPrice17.7555USD, canPresale997,
overseas1057; non garanzia stockassemblaggio. PCBtarget85×35 richiede ripiazzamento:
screening corpi conservativo non trova collocazione eMMC senza conflitti.
Leggere README esperimento e report prima di integrare. Nessun commit eseguito.

## Checkpoint software USB web/password — 2026-11-15

ROCK release firmata 7-e5be66d837ffa82f; http://192.168.7.1 → HTTPS USB,
password iniziale phoenix con cambio obbligatorio, lockout 3 errori/5 minuti.
Dettagli, test e certificato in platforms/linux/deploy/USB_ADMIN.md.
Nessuna password personale impostata dall’agente; nessun commit/push in questa
sessione. CAD invariato rispetto al checkpoint precedente. Gate VBUS di banco
non reso permanente: resta necessaria qualifica elettrica/bootloader.

## Checkpoint finale hotspot — 2026-11-15

ROCK: release 10-91dfb3026f3ceaba, controlli hotspot installati. Off/on verificati
senza perdere USB/VPN, hostapd ENABLED su Phoenix-Test canale6; ricezione dal
telefono ancora da confermare. Ether ora 192.168.1.28: non assumere IP storico.
107 test Linux e build ESP32 passati. Upload release8 verificato viaVPN:
285.06/73.99 Mbps download/upload su server diversi. Temperatura in Sistema.
Dettagli BRINGUP.md e deploy/HOTSPOT.md. Nessun commit/push richiesto ora.
USB durante update non si è ripresa automaticamente per l'utente: reinserimento
cavo necessario, causa non qualificata. Le modifiche AP non hanno interrotto USB.

Hotspot: telefono ancora non vede la rete. Mac CoreWLAN scan rileva nome
Phoenix-Test a -90 dBm, canale6 (BSSID redatto). Radxa specifica antenna esterna
obbligatoria per 4C+; domanda sull'antenna attualmente pendente. Fonte e caveat
in BRINGUP.md. Priorità verificare antenna prima di altre modifiche software.

## Chiusura sessione — 15 novembre 2026

Utente conferma: antenna esterna prima scollegata; dopo collegamento vede
Phoenix-Test e conferma funzionamento dal telefono. Hotspot verificato quindi
anche dal client, oltre a hostapd. Lavoro sospeso su richiesta dell’utente;
commit/push software e checkpoint hardware richiesti. Nessun ulteriore ordine,
flash o modifica hardware. Resta la qualifica elettrica USB/VBUS e del reboot.
