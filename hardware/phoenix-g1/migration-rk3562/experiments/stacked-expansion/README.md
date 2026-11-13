# Espansione sovrapposta — sostituzione J3

Stato: **schema integrato, piazzamento e blocco locale di protezione parzialmente instradati e verificati**.
Il derivato corrente è indicato da `working-candidate.json`.
Non pronto per fabbricazione. Il checkpoint precedente `../lpddr4-1gb/working-board.json`
resta immutato; questo candidato va completato prima di promuoverlo.

## Fissaggi obbligatori — riserva CAD

Aprire `mechanical/mounting-reservations.kicad_pcb`, layer **Dwgs.User**:
H8101 (53;4) e H8102 (83;3) mm, due posizioni asimmetriche rispetto a J3.
Cerchio interno: futuro foro NPTH 2,2 mm per M2; esterno: riserva 5,4 mm
su entrambi i lati per testa vite/distanziale e margine. Distanza PCB nominale
3,5 mm, da abbinare alle tolleranze DF40; nessun distanziale commerciale
ancora selezionato. La coppia di fori da sola non certifica l'anti-inversione.

**Non sono fori già realizzati**: l'overlay segnala le riserve e non genera
forature. Per liberarle vanno ricollocati C422/C425/R1811 presso H8101 e
C445/C470/L405/R431 presso H8102. Nessuna pista/via esistente attraversa
le riserve nella verifica geometrica attuale. Zone rame da tenere escluse
quando si creeranno i fori. `mechanical/mounting-interface.json` registra
questi blocchi: risolverli è obbligatorio prima del rilascio e prima di
progettare la figlia. Riconvalidare tutto nel passaggio a 85×35 mm.
Rigenerare l'overlay con `tools/reserve_stacked_mounts.py` dopo ogni
variazione del candidato. Il PCB elettrico precedente resta invariato.

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

## Riserve ausiliarie H8103–H8105

Aggiunti tre punti M2 provvisori, oltre ai due della scheda figlia, nel medesimo
overlay `mechanical/mounting-reservations.kicad_pcb` (Dwgs.User).
La mappa `mechanical/mounting-overview.svg` mostra la distribuzione proposta.
- H8103 (21;3): staffa/case lato USB.
- H8104 (37;31): possibile staffa per dissipazione; interferisce con clock,
  test point e condensatori. Priorità all'integrità elettrica: spostare la
  riserva anziché il clock se il successivo layout lo richiede.
- H8105 (70;34): appoggio staffa/case lato Ethernet.

Riserve da 5,4 mm, futuro NPTH 2,2 mm; nessuna foratura reale introdotta.
21 riferimenti interferiscono con le tre nuove riserve, censiti nel JSON.
Il controllo geometrico non trova piste/via nelle riserve, ma le zone rame
non sono escluse e le quote devono essere riconvalidate dopo la compattazione.
Non è un fissaggio diretto standard per una ventola: servirebbe una staffa
adattatrice. Non è stato aggiunto un circuito elettrico per alimentarla.
Raffreddamento passivo prioritario. Evitare carico concentrato sul BGA,
verificare flessione PCB, pressione del thermal pad, isolamento e accesso viti.
I 3,5 mm della scheda figlia non definiscono l'altezza delle staffe ausiliarie.

## Avanzamento collegamenti locali — checkpoint corrente

Ripartire da `working-candidate.json`: `pcb/logic-reference.kicad_pcb`, verificato
in `pcb/logic-reference-audit.json`. Il PCB principale LPDDR4 rimane invariato.

- Riposizionati i sei passivi U8101, senza cambiare netlist o componenti.
- Tutte e quattro le reti locali ILIM/dVdt/EN/fault collegate ai rispettivi
  passivi; dVdt accorciata da 7,79 a 2,83 mm.
- Sette pad GND collegati al piano esistente, continuità verificata fino a
  U4.69; altri pin GND del PMIC restano incompleti nel progetto generale.
- Collegati i due pin IN al condensatore di ingresso e OUT al condensatore
  di uscita. Tracce locali 0,3 mm: non è una qualifica di portata/temperatura.
- R8102.2 collegata alla linea +3V3_IO U4.55 con un nuovo via e percorso
  interno In2.Cu. Continuità verificata, 14,81 mm nominali di percorso.
- 2460 piste/via originali preservati, 114 nuovi segmenti/via nel derivato.
- DRC invariato: 125 via dangling e 14 difetti serigrafia preesistenti,
  nessun nuovo corto/clearance/courtyard. 499 airwire riportati, conteggio
  potenzialmente limitato. Non significa completamento della scheda.

Restano alimentazione d'ingresso del ramo, uscita verso J3, GPIO fino al SoC,
coppia USB, budget energetico e qualifica elettrica/termica. I fissaggi
restano riserve non liberate; eMMC/display/comando e compattazione sono aperti.
I render precedenti non rappresentano questo ultimo piazzamento.

Catena riproducibile (Python KiCad): `route_stacked_control.py`,
`route_stacked_ground.py` (con --input/--output/--report),
`route_stacked_local_power.py`, `route_stacked_fault_supply.py`.
Eseguire DRC sul risultato e `audit_stacked_local_power.py fault-supply`.
Gli output intermedi mantengono i rispettivi limiti e non sono checkpoint finali.

Il tentativo `mechanical/mount-clearance-trial.kicad_pcb` è SCARTATO:
spostava troppo lontano alcuni passivi di potenza e non liberava due componenti.
Non usarlo come base di routing. Le riserve restano nel relativo overlay.

## Vincoli USB e fabbricazione

La [guida ufficiale JLCPCB](https://jlcpcb.com/help/article/user-guide-to-the-jlcpcb-impedance-calculator),
consultata il 13 novembre 2026, lega il calcolo a stack-up, strato, riferimento,
rivestimento e geometria. Il record JLC06161H-3313 del progetto è ancora un
candidato: non definisce larghezza/gap USB qualificati. Il tentativo di usare
il calcolatore interattivo è impedito dal browser host non disponibile in
questa sessione. Non sono stati inventati o applicati valori di impedenza.

## Avanzamento successivo: alimentazione e controlli fino a J3

Il derivato `logic-reference` completa geometricamente:
- ingresso eFuse dalla rete +5V_MAIN esistente;
- uscita eFuse agli otto contatti +5V_ADDON di J3;
- quattordici contatti GND J3 al piano esistente;
- abilitazione e fault U1.K2/U1.L3 ↔ J3.27/J3.28 ↔ eFuse;
- riferimento +3V3_IO al contatto J3.36.

R8102 ora ruotata di 180° per separare l'uscita fault dal suo pull-up.
747 segmenti/via nuovi rispetto al candidato originario; tutti i 2460
precedenti preservati. DRC resta alle stesse 139 violazioni preesistenti.
Collegamento non equivale a qualifica di portata: alimentazione interna
1 mm su In3, colli esterni 0,3 mm, via 0,6/0,3 mm e dita J3 0,15 mm sono
candidati con verifica termica/caduta/tolleranze e budget USB ancora aperti.
La corrente nominale del limite di protezione non è un budget di carico LTE.

Regole aggiunte, esplicite nei .kicad_dru: 0,17 mm di clearance solo contro
pad J3; 0,15 mm di larghezza minima per dita +5V_ADDON; 0,0762 mm per
escape GPIO dal BGA. Le piste lontane dal connettore conservano 0,20 mm di
clearance. Escape BGA vincolati al processo sperimentale già usato dalla DDR:
nessuna qualifica di fabbricazione o integrità del segnale implicita.
Istruzioni precedenti che descrivono feed/GPIO aperti sono storiche.

## Riserve meccaniche applicate al rame

`protect_stacked_mounts.py` genera `pcb/mount-protected.kicad_pcb` da cui
riparte la catena di routing. H8101–H8105 sono rule area su tutti e sei gli
strati: vietati nuove piste, via e riempimenti. I componenti che occupano
le riserve sono ancora da ricollocare; i fori non sono creati. Le rule area
non vietano pad/footprint esistenti, per distinguere quel lavoro irrisolto
dalla protezione del nuovo routing.

Il checkpoint `logic-reference` è stato rigenerato con tali zone: tutti i
controlli end-to-end passano, DRC invariato. Nel piazzamento aggiornato C8103
è (79;4,2) mm/180°, R8103 (82,5;9,5) mm/0°, R8102 (73;6,5) mm/180°.
Il report JSON attuale prevale sui conteggi e sulle coordinate storiche.

`tools/rebuild_stacked_expansion.py` ricostruisce i passaggi in sequenza,
interrompendosi su fallimento del tool o nuove violazioni DRC; promuove il
checkpoint solo dopo la verifica di tutte le connessioni richieste e delle
cinque riserve. Lo stadio intermedio output-bus ammette un via dangling
aggiuntivo, che deve scomparire allo stadio output-feed.

`tools/route_stacked_aux_io.py` è un esperimento separato: ogni rete viene
accettata soltanto dopo continuità e DRC; le altre vengono scartate. Non
qualifica SPI/UART/I2C né il processo delle piste BGA a 3 mil, e non
completa la coppia USB. L'audit finale deve precedere la promozione.


## Checkpoint 13 novembre — segnali ausiliari e riserve meccaniche

Il puntatore `working-candidate.json` ora seleziona `pcb/aux-io.kicad_pcb`.
L'audit preserva tutte le 2.460 piste/via originali e le reti dei pad; aggiunte
1.591 primitive, non 1.591 reti. Le 139 violazioni DRC preesistenti sono invariate.
Cinque riserve meccaniche impediscono nuove piste/via/riempimenti, ma non sono
fori reali e contengono ancora componenti da riposizionare.

Alimentazione protetta, masse, riferimento logico e GPIO enable/fault sono
collegati. Dei segnali aggiuntivi risultano collegati SCL, SPI_CLK, MOSI, CS0.
SDA, MISO, CS1, UART TX/RX e GPIO2/3 restano aperti; USB non instradata.
I tentativi `aux-io-second` e `aux-io-fine` non hanno aggiunto percorsi e non
sostituiscono il checkpoint. La ricerca limitata non dimostra impossibilità
fisica: occorre rivedere il fanout completo del connettore, evitando di occupare
prima i corridoi necessari ai pad adiacenti.

`rebuild_stacked_expansion.py` ricostruisce fino a `logic-reference` e riporta
il puntatore a quel livello. Per riprodurre lo stadio successivo eseguire
`route_stacked_aux_io.py`, quindi `audit_stacked_local_power.py aux-io` con
Python KiCad; promuovere soltanto dopo controllo del report e SHA.
Il candidato eMMC è separato in `../emmc-system`: schema aggiornato, PCB ancora
con NOR. Non utilizzare netlist e PCB dei due candidati come coppia di produzione.

Studio meccanico `mechanical/mount-local-trial.json`: ricerca di spostamenti
entro 4 mm sullo stesso lato; solo R1811 trova una posizione libera, senza nuovi
DRC. Gli altri sei componenti presso H8101/H8102 richiedono una revisione locale
più ampia. Studio non promosso; nessun foro creato.

Il tentativo `aux-io-wide` non è promosso: nella versione sperimentale del
selettore di strato mancava In3 dalla verifica delle via. Il DRC ha respinto
il percorso e preservato il checkpoint; il generatore ora verifica sempre
i sei strati distinti, indipendentemente dallo strato di routing scelto.

## Inventario senza limite del report DRC

`inventory_stacked_connectivity.py` usa la connettività dei pad, senza affidarsi
al limite degli elementi mostrati dal DRC. Sul checkpoint aux-io: 276 reti,
269 reti con più pad,231 reti ancora suddivise in gruppi. GND ha 582 pad e 471 gruppi.
Il report è `pcb/connectivity-inventory.json`, legato allo SHA del PCB.
Questi numeri non sono percentuali di completamento né qualifiche elettriche.

Anche i tentativi conclusivi `aux-io-back` e `aux-io-small-via` non hanno
aggiunto reti: il secondo usa via 0,45/0,20 mm entro le regole esistenti.
L'audit finale conferma il checkpoint precedente, senza nuove violazioni.
Non ripetere questi tentativi invariati: occorre modificare la disposizione
delle uscite del connettore o il relativo fanout, poi ripetere i controlli.
