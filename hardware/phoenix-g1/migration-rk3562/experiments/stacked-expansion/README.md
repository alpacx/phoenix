# Espansione sovrapposta — sostituzione J3

Stato: **schema integrato e piazzamento verificati, nuove reti NON instradate**.
Non pronto per fabbricazione. Il checkpoint precedente `../lpddr4-1gb/working-board.json`
resta immutato; questo candidato va completato prima di promuoverlo.

## Scelta e posizione

J3 sostituisce il precedente PZ127 2×10: non aggiunge un secondo connettore.
Base Hirose DF40C-40DP-0.4V(51), JLC C424643; controparte sulla futura
scheda accessoria DF40HC(3.5)-40DS-0.4V(51), JLC C3020022.
40 contatti a passo 0,4 mm, distanza nominale tra PCB 3,5 mm.
Corpo base 9,52×2,97 mm; courtyard 10,1×3,9 mm.
Centro sul PCB: (67,5; 2,5) mm, lato superiore, vicino a Ethernet.
Tre condensatori non instradati (C423/C431/C435) passano al retro alle stesse
coordinate. La qualità del loro futuro collegamento di alimentazione resta da verificare.
Il PCB candidato conserva **90×40 mm**; il target **85×35 mm** non è ancora validato.

Il connettore non è polarizzato: servono fissaggi asimmetrici o una chiave
meccanica. La scheda figlia deve evitare il corpo RJ45 e lasciare spazio al
raffreddamento passivo; 3,5 mm NON autorizzano una scheda piena sopra tutti i
componenti. Sagoma, fissaggi, altezza totale e assemblabilità da verificare.

## Interfaccia

`pinout.json` definisce la numerazione custom Phoenix, non uno standard HAT.
USB 2 host dedicata RK3562: AE26 DM e AE27 DP; USB-C device invariata.
Sono disponibili I2C, UART, SPI e quattro GPIO a logica 3,3 V.
GPIO0 abilita l'alimentazione; GPIO1 legge il fault. Due contatti restano NC.
Il modem, la eSIM, i regolatori e l'eventuale adattamento livelli sono sulla
scheda accessoria futura: non sono inclusi in questo progetto.

Otto contatti portano +5V_ADDON, ma la corrente nominale di 0,3 A per contatto
non dimostra un budget di sistema di 2,4 A. Il ramo TPS259531 è disabilitato
all'avvio tramite pull-down e ha un limite preliminare di circa 0,99 A.
Il budget USB d'ingresso deve alimentare anche tutta la scheda base: non è
ancora dimostrato che basti per un modem LTE, soprattutto nei picchi.
Non collegare a caldo e non alimentare esternamente la scheda accessoria.
MP1–MP4 sono soli ancoraggi meccanici. La controparte richiede verifica della
corrispondenza speculare dei contatti prima del layout della scheda figlia.

## Evidenze e costi

Snapshot JLC in `sourcing/`, osservati il 13 novembre 2026:
- C424643: canPresaleNumber 12913, prezzo iniziale 0,5367 USD.
- C3020022: canPresaleNumber 1991, prezzo iniziale 1,1518 USD.
Totale indicativo coppia 1,6885 USD; non include PCBA, spedizione, imposte,
protezione di alimentazione né scheda figlia. I campi di stock non si sommano
tra loro e non garantiscono disponibilità immediata per un ordine PCBA.

Dimensioni dal catalogo Hirose locale `hirose-df40-catalog.pdf`, pagine 7 e 10;
[scheda ufficiale base](https://www.hirose.com/en/product/p/CL0684-4013-7-51).
Footprint con numerazione Phoenix: da qualificare con i componenti reali.
La regola DRC da 0,17 mm vale SOLO fra pad dello stesso J3 (passo 0,4 mm,
land 0,23 mm), senza ridurre la clearance generale.

`audit.json`: 71 disposizioni pin schema/PCB verificate; 2460 segmenti/via
preservati; UUID distinti; reti originali invariate salvo i due pin host prima NC.
DRC: nessun corto/clearance/courtyard aggiuntivo; restano 125 via dangling e
14 problemi serigrafia preesistenti. 499 elementi non connessi riportati:
possibile limite di report, non misura del totale residuo.
ERC: 15 power_pin_not_driven e una isolated_pin_label; NON pulito.

## Lavoro ancora necessario

Instradare USB host a impedenza controllata e ramo di alimentazione; qualificare
protezione ESD, dissipazione e picchi del modem; assegnare MPN ai passivi nuovi
ed aggiornare disponibilità del ramo di potenza. Integrare separatamente eMMC,
display e comando, poi compattare sul target. Progettare controparte, chiave
meccanica e fissaggi prima di ordinare. Nessuna simulazione SI/PI o prova fisica.

## Riproduzione

1. `tools/build_stacked_expansion.py` con Python + sexpdata.
2. Esportare `system/kicad/integrated/phoenix-g1.kicad_sch` con KiCad CLI
   `sch export netlist --format kicadxml` in `system/review/netlist.xml`.
3. `tools/place_stacked_expansion.py` con Python KiCad pcbnew.
4. KiCad CLI `pcb drc --format json` in `pcb/drc.json` e
   `sch erc --format json` in `system/review/erc.json`.
5. `tools/audit_stacked_expansion.py` con Python KiCad pcbnew.

Gli script riscrivono solo questa directory candidata; non il PCB sorgente.
