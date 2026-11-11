# Phoenix G1 — migrazione RK3562 in corso, non ordinabile

## Requisiti attivi

**Aggiornamento: cambio a RK3562 autorizzato.** Il lavoro nuovo è in `migration-rk3562/`; lo schema integrato precedente resta RK3568 e non rappresenta la migrazione completata. La revisione precedente è conservata in `archive/rk3568-before-rk3562-migration.tar.gz`. RAM512MiB e funzioni restano confermate. I conteggi e il costo sottostanti descrivono la baseline RK3568 finché non è integrato il nuovo processore.

## Migrazione RK3562 — verifica integrata aggiornata

Progetto attivo: `migration-rk3562/kicad/integrated/phoenix-g1.kicad_sch`. **41 fogli, 1.775 disposizioni di pin confrontate, zero differenze di trascrizione.** La trascrizione non costituisce una revisione elettrica indipendente. I controlli restano distinti dalla qualifica e dal collaudo.

Dei 478 ball del processore: 380 hanno una rete assegnata, 96 sono intenzionalmente non collegati e **2 restano PENDING: DDR_RZQ (1D4), DDR_VREFOUT (1C9)**. Le reti comprendono 136 segnali attivi, 229 pin di alimentazione/massa e 15 ingressi ADC inutilizzati collegati a massa. I 96 NC comprendono 53 GPIO non utilizzati, 38 segnali di interfacce escluse dal progetto, quattro uscite DDR non necessarie e USB ID per il ruolo fisso periferica. Sono decisioni del progetto, non certificazione del circuito; i vincoli firmware sono registrati in `pending-pin-audit.json`.

Per USB ID, il TRM Part1 PDFp391 documenta il pull-up abilitato al reset e il controllo IDDIG. Il firmware deve mantenere il ruolo peripheral/UFP e non attivare VBUS host. Per DDR, il datasheet H5TQ2G63GFR specifica A0..A13 nella configurazione x16: A14/A15 e le uscite della seconda rank non hanno carichi nella configurazione scelta. Bootloader e training devono gestire una rank da 32 bit.

**ERC: 18 segnalazioni** (4 etichette isolate, 14 ingressi di alimentazione senza un power_out sulla stessa rete). Nessun nuovo conflitto rilevato dopo aver modellato le direzioni dei 136 segnali attivi. Sono rintracciati percorsi DC per tutte le 26 reti con ingressi di potenza; questo non verifica tensioni, enable, sequenze, corrente o stabilità. Non sono aggiunti PWR_FLAG o esclusioni. I PHY analogici non usati restano alimentati alle tensioni nominali; non viene presunto che si possano lasciare flottanti.

134 assegnazioni funzione/ball sono corroborate da uno schema originale pubblico del progettista Oomwoo; le due del quarzo non sono estratte da quel controllo. È un riferimento di terzi LPDDR4, non una scheda DDR3 qualificata da Rockchip. Il datasheet RK3562 Rev2.1 e il TRM sono archiviati con provenienza; non sostituiscono le prescrizioni mancanti per DDR3 e sequenza di avvio.

R1405/FLASH_VOL_SEL del RK3568 è rimosso nella nuova variante. Il feedback CPU si chiama CPU_FB_SENSE e non presume un ball remoto assente sul RK3562. RK860 prescrive il rilevamento lato condensatore; valori RC e stabilità restano da qualificare.

La distinta contiene 340 posizioni con candidati selezionati e 14 test land, con quantità riconciliate. Il controllo JLCPCB dei componenti principali è in `migration-rk3562/sourcing/critical-stock-refresh.json`: canPresaleNumber 94 per RK3562, 19 per RAM, 2007 per RK809-5 e 6376 per AP6256. Non sono riserve né garanzie di disponibilità immediata per PCBA. Il costo non include una qualifica o un preventivo definitivo dell'assemblaggio.

Il footprint candidato a 478 pad supera caricamento e salvataggio KiCad, ma non è assegnato al processore né qualificato. Una pista da 3 mil fra pad adiacenti da 0,25 mm non soddisfa le distanze nominali considerate. **Piazzamento e routing della variante non sono completati.** Restano inoltre disaccoppiamento/PI, display e relativo montaggio, termica passiva, firmware/boot, SI e revisione per fabbricazione. Non è stata eseguita alcuna prova fisica del PCB custom.

Rigenerazione: `python3 hardware/phoenix-g1/tools/rebuild_rk3562.py`, con KiCad e ambiente sexpdata esistenti. Aggiorna schema, netlist, ERC, confronti, percorsi DC e distinta; non genera file di produzione. Stato analitico in `migration-rk3562/review/completion-status.json`.

### PCB RK3562: alimentazione e controlli USB

Il PCB dedicato è `migration-rk3562/kicad/pcb/phoenix-g1.kicad_pcb`, con 353 footprint, 1356 segmenti di pista e 139 vias. Il report `pcb-connectivity-check.json` contiene conteggi e hash del file verificato. **1.774 pad corrispondono alla netlist, senza differenze di rete o violazioni DRC geometriche. Restano 1122 collegamenti del ratsnest e i 13 pad del display da implementare.** Il limite di 499 connessioni mostrate dal DRC non è il totale: il conteggio deriva dalla connettività del PCB.

Sono verificate per continuità fisica tutte le 18 reti di controllo/rilevamento USB e ausiliarie. Il controllo segue pad, piste e vias del PCB salvato. Le piste di segnale sono da 0,20 mm; i vias ordinari usano land/foro 0,60/0,30 mm e quelli CC e alcuni altri segnali 0,45/0,20 mm. In3.Cu ospita anche alcuni segnali di controllo; In2.Cu ospita le dorsali candidate VBUS_RAW e VBUS_PROTECTED da 1,50 mm. Restano da ottimizzare percorsi, ritorni ESD e qualificazione elettrica.

**Entrambe le reti VBUS_RAW e VBUS_PROTECTED sono continue verso tutti i rispettivi pad.** Questo comprende i quattro contatti VBUS di J1, i pin IN/OUT della prima protezione U24, gli ingressi U15, i partitori, TP2 e gli ingressi ausiliari U11/U6. Le diramazioni di rilevamento e alimentazione ausiliaria da 0,20 mm non sono percorsi per la corrente del carico principale. Anche +3V3_AON è continua dall’uscita di U11 a tutti i pin assegnati a questa rete. La distribuzione +5V_MAIN verso tutti i carichi non è completata.

Sono controllati 13 condensatori: i sei bypass di U11/U15/U24, i sei di U12/U13/U14/U16/U19/U6 sulla linea ausiliaria e C605 sull’ingresso VBUS di U6. Dodici sono sul lato dei rispettivi integrati; C605 resta sul retro. Tutti sono collegati ai pin corrispondenti, senza qualificare per questo l’impedenza dei percorsi. Sono verificate le uscite in rame e la continuità dei 48 pad GND dei quattro fogli USB controllati verso tutti e quattro i contatti GND di J1, attraverso due piani candidati In1.Cu/In4.Cu. Questa verifica geometrica non certifica induttanza, impedenza, portata o temperatura. Gli altri condensatori e ritorni della scheda richiedono ancora lavoro.

Dodici vias termici candidati seguono gli esempi TI RVC0020A/RNH0030A: land/foro 0,45/0,20 mm. Riempimento/plugging, stencil e costo di assemblaggio non sono qualificati. Nessuna esclusione DRC è stata aggiunta. Il piazzamento è fissato in `placement-seed.json` per evitare spostamenti involontari dei gruppi non interessati.

`usb-power-dc-screen.json` confronta analiticamente le sole dorsali larghe VBUS_RAW, VBUS_PROTECTED e +5V_MAIN con rame nominale da 17,5 e 35 µm a temperature imposte. Non è una simulazione termica: esclude restringimenti, vias, connettore e resistenza degli interruttori. `aon-output-capacitance-screen.json` registra il controllo del condensatore C1102 sulla curva tipica YAGEO e il limite di capacità effettiva TI; restano bias/temperatura/invecchiamento da qualificare. Non sono cambiati i codici componente della BOM.

I tentativi precedenti scartati e la successiva revisione accettata come bozza parziale sono registrati in `usb-power-routing-trials.json`. Le viste dei sei strati rame sono in `migration-rk3562/review/pcb-views/`. Il controllo `tools/check_rk3562_release.py` confronta gli hash dei report con il PCB e mantiene il progetto **bloccato per fabbricazione**: DRC geometrico superato non significa scheda completata.

La richiesta tecnica al fornitore, preparata ma non inviata, è `migration-rk3562/review/manufacturer-information-request.txt`: mancano prescrizioni RK3562 specifiche per DDR3 RZQ/VREF, sequenze PMIC e package FCCSP478. I riferimenti RK3568 non qualificano questi aspetti. Restano inoltre routing USB dati/DDR/Ethernet e alimentazioni, footprint/montaggio display, stackup/escape, SI/PI, firmware di avvio e prove termiche passive. Nessun prototipo custom è stato provato.

Corretti i contorni di assemblaggio di 26 istanze in 20 file delle librerie locali RK3562, mantenendo invariati pad e fori. Il controllo `courtyard-envelope-audit.json` verifica che tutti i pad siano racchiusi dai contorni; questo è un requisito geometrico necessario, non una qualifica completa di package, tolleranze o processo di montaggio. Le correzioni sono conservate anche in `migration-rk3562/overrides/footprints/`; il riuso delle librerie verifica gli hash originali prima di applicarle. La baseline RK3568 non è stata modificata. La ricerca dei percorsi considera ora la distanza dal bordo del rame, incluso il raggio dei vias, mantenendo 0,25 mm di clearance.

Il contorno resta 90 × 40 mm; sei strati e 1,6 mm sono provvisori. Rigenerazione: `python3 hardware/phoenix-g1/tools/rebuild_rk3562_physical_draft.py`. Esegue DRC anticipato, routing, riempimento dei piani e controlli finali di continuità. **Sovrascrive il PCB generato: preservare modifiche manuali prima di eseguirlo e non usare editor concorrenti durante la build.** Se una fase o una verifica fallisce, vengono ripristinati PCB, floorplan e report precedenti. Non produce Gerber o ordini.

### Convertitore Wi-Fi — aggiornamento 9 novembre

Riorganizzato il gruppo U26/TPS62130 con induttore, condensatori e partitore vicini all'integrato. Le modifiche e gli spostamenti dei componenti adiacenti ancora non instradati sono registrati in `wifi-converter-placement.json` e fissati in `placement-seed.json`. Nessun valore, MPN o collegamento dello schema è cambiato.

Sono instradate e verificate le sette reti locali del gruppo, inclusi SW, feedback, VOS, soft-start e power-good. AGND/PGND e le masse dei condensatori principali raggiungono direttamente il pad esposto sul rame frontale; i ritorni raggiungono i quattro contatti di massa USB tramite i piani. Tre vias termici sono candidati, con processo di riempimento/stencil ancora da qualificare. I collegamenti di potenza locali sono sul frontale; i segnali di rilevamento sul retro sono distinti dalle piste di carico. Il segnale WIFI_VBAT_PG raggiunge anche U17.13, abilitazione del regolatore di sistema.

C1304 è stato avvicinato al gruppo L1301/C1305 per liberare l’uscita principale; posizione e tentativi scartati sono in `wifi-input-supply-placement.json` e `wifi-input-supply-trials.json`. Il passaggio di potenza viene riservato prima dei segnali, così la rigenerazione non lo blocca.

Il controllo indipendente `wifi-converter-copper-audit.json` verifica il rame salvato e i collegamenti esterni ancora mancanti. Il condensatore d'ingresso C2201 è a 2,2472 mm dal centro del pad PVIN; questa distanza non è una misura dell'induttanza del circuito. L’ingresso del gruppo raggiunge ora l’uscita U15.5 tramite una dorsale In3.Cu da 1,50 mm, lunga 47,7261 mm, con due vias da 0,60/0,30 mm per estremità e raccordi esterni da 0,50 mm. La capacità di corrente e la temperatura non sono qualificate. L’uscita raggiunge ora la ferrite FB2001 e il pin VBAT del modulo, con C2001/C2002 e le rispettive masse collegati. Restano non collegati gli altri carichi della linea principale e incompleto il resto del circuito Wi-Fi: non è un’alimentazione funzionante completa. Il componente C2204 è nominalmente da 22 µF/16 V, C2201 da 10 µF/25 V; capacità effettive, stabilità e termica sono ancora aperte in `wifi-converter-electrical-review.json`.

Rigenerazione dei percorsi di alimentazione e successiva integrazione delle masse superate: **1218 segmenti, 133 vias, 1129 collegamenti mancanti, zero violazioni DRC geometriche**, senza regressioni delle 18 reti di controllo USB o delle alimentazioni/masse USB già verificate. Le prove negative eliminano, in copie separate, la pista di abilitazione U17.13 e la dorsale d’ingresso: l’audit rileva entrambe le interruzioni pur mantenendo intatti i nomi delle reti. Nessuna simulazione elettrica o prova fisica eseguita.

Disponibilità pubblica JLCPCB aggiornata per gli otto codici del gruppo: quantità ordinabili osservate positive; nove componenti per circa **1,3203 USD** a prezzi 1+. Non sono riserve né conferme PCBA. Il ricalcolo parziale dell'intera BOM, applicando questi prezzi a tutti i loro impieghi e mantenendo le date precedenti per gli altri codici, porta il subtotale a **67,4095 USD**. Sono esclusi PCB, assemblaggio, acquisti minimi, scarti, trasporto, involucro e imposte. Evidenze in `sourcing/wifi-converter-stock-refresh.json` e `sourcing/cost-update-wifi-refresh.json` della variante attiva. Il budget di 50 EUR assemblati non è dimostrato.

## Baseline conservata

RK3568, **512 MiB DDR3 (due dispositivi x16)**, Ethernet Gigabit, una USB-C per alimentazione e USB 3 device verso il Mac, Wi-Fi integrato con antenna esterna, piccolo display a colori non touch e connettore interno per espansioni. Nessun 5G. **Raffreddamento passivo obbligatorio: nessuna ventola.** Il contorno resta **90 × 40 mm**. Gli studi LPDDR4 e 100 × 30 mm sono alternative archiviate, non la configurazione attiva.

L'altezza di 18–22 mm ipotizzata per l'involucro è una stima: display, flex, dissipatore, distanziali e tolleranze non sono ancora verificati insieme.

## Stato verificato l’8 novembre 2026

Lo schema gerarchico comprende 37 fogli funzionali più la radice, **355 componenti fisici** e 1.935 disposizioni di pin controllate contro i contratti degli script. ERC: **0 errori, 1 avviso** per USB_SHIELD isolato. I contratti verificano la trascrizione prevista, non costituiscono una revisione indipendente del circuito.

Il PCB contiene **354 footprint, zero piste e 1.354 connessioni mancanti**. Manca il footprint qualificato del display. Il posizionamento automatico è uno studio di ingombro, non un layout elettrico. Dopo aver riservato entrambi i lati anche per i fori termici del PMIC, il DRC riporta **0 violazioni geometriche**; mostra separatamente 499 connessioni mancanti, elenco limitato rispetto al conteggio completo. Nessuna esclusione aggiunta per nascondere errori.

Lo screening dei 31 pad forati controlla dimensioni e anelli di rame nominali. Non copre tolleranze di foratura, distanza fra fori, maschera, assemblaggio, impedenza o fit meccanico. I fori termici del PMIC sono al minimo nominale di 0,15 mm di anello: il processo resta da qualificare.

**La scheda non è pronta per produzione.** Non sono stati generati Gerber o file d'ordine; non è stato costruito né provato un prototipo custom.

## File da aprire

- `kicad/integrated/phoenix-g1.kicad_pro`: schema completo da revisionare.
- `kicad/floorplan/phoenix-g1-floorplan.kicad_pcb`: studio di posizionamento non instradato.
- `review/release-gate.json`: condizioni ancora aperte per il rilascio.
- `review/integrated-erc.txt`, `integrated-connectivity.json`, `floorplan-drc.txt`, `floorplan.json`: controlli correnti.
- `review/fabrication-screen.json`: screening dimensionale limitato dei fori e anelli.
- `review/bom-inventory.json`: inventario di 355 riferimenti, non BOM per ordine.
- `sourcing/selected-main-parts.json`: prezzi e quantità dei candidati selezionati.
- `sourcing/public/`: osservazioni delle pagine JLCPCB, incluse alternative non selezionate.

I fogli autonomi sono sorgenti generati; aprire la gerarchia integrata per seguire i collegamenti. Anteprime eventualmente presenti non sostituiscono i file KiCad e i rapporti correnti.

## Circuiti e verifiche recenti

- **Wi-Fi AP6256**: SDIO, controllo accensione, clock a 37,4 MHz e 32,768 kHz, alimentazioni e U.FL nello schema. Pinout confrontato con modulo e riferimento Radxa ROCK 3C. BT disabilitato. Restano RF a 50 ohm, keepout, clock, sequenza di alimentazione, driver/firmware e modalità access point da qualificare.
- **Alimentazione Wi-Fi**: aggiunto U26 TPS62130RGTR, regolatore dedicato da **3,584 V**, con ferrite TDK da 20 mΩ. Il suo PG, riferito alla propria uscita, abilita il regolatore di sistema U17. Lo screening statico PWM comprende tolleranze dei resistori e leakage del feedback e lascia **210 mV** sul minimo VBAT di 3,2 V. Restano esclusi transitori, temperatura dei passivi, perdite delle piste e dropout con USB bassa; PG non garantisce lo spegnimento sicuro in ogni guasto. Vedere `wifi-power-check.json`.
- **Espansioni**: header 2×10 a passo 1,27 mm, SPI, I²C, UART e quattro GPIO a 3,3 V; pinout Phoenix, non compatibile HAT/PMOD. Candidato C3975193: 0,1745 USD, corpo 12,7×3,4 mm, riserva preliminare 14×8 mm. Corrente disponibile per espansioni non allocata; niente hot-plug o alimentazione esterna sui rail. Altezza e controparte ancora da qualificare. Vedere `expansion-pinout.json`.
- **Reset termico**: collegamento TSADC_SHUT_M0 → 0 Ω → RESETn/RESETB coerente con il riferimento Rockchip. Software e comportamento reale del PMIC ancora da provare; vedere `reset-path-check.json`.
- **DDR3**: H5TQ2G63GFR-TEC, 1,50 V. Feedback PMIC con resistori 0603 da 0,1%, 25 ppm/°C selezionati. Target iniziale 533 MHz / 1066 MT/s, non un risultato misurato né il limite del componente. Il loader e la topologia a due chip devono essere verificati.

## USB, stackup e alimentazione

Il nuovo candidato USB-C è **Molex 2012670005, C565324**, per PCB da **1,6 mm**: 24 contatti, quattro asole metallizzate larghe 0,6 mm, nessun foro non metallizzato. Lo schema e il footprint sono aggiornati. Il conflitto precedente fra connettore da 0,8 mm e spessori JLC a sei strati è risolto nella bozza. Restano da scegliere materiali e spessori dielettrici effettivi e da qualificare impedenza e assemblaggio. Il disegno locale revisione C è stato ispezionato; della C4 corrente sono confrontate le quote testuali, non ancora la grafica completa. Vedere `usb-201267-footprint.json` e `stackup-compatibility.json`.

HD3SS3220 gestisce USB-C UFP/SuperSpeed; non c'è negoziazione USB PD. Il carico principale viene abilitato solo quando la sorgente pubblicizza 3 A Type-C. Non è garantito l'avvio da qualsiasi porta Mac. TPS25940 protegge il ramo VBUS e TPS259531 il carico principale: budget completo, accensione, spegnimento, brownout e dissipazione restano aperti. Lo screening della rampa di 66,2 µF nominali indica circa 126 mA capacitivi durante 2,62 ms tipici, senza includere l'avvio di tutti i carichi.

USB, DDR e RGMII richiedono ancora stackup, escape BGA, vincoli di temporizzazione, piani e routing. Inventario e griglia relativa dei 636 ball RK3568 sono verificati. Il footprint revisionato corregge gli arrotondamenti alla griglia esatta di 0,65 mm; l'orientamento è confrontato con le viste top/bottom del datasheet Rockchip V1.0. Resta da riconciliare la revisione del package realmente ordinato e qualificare land, maschera, stencil ed escape. Un via 0,4/0,2 mm al centro di quattro ball viola il target di clearance da 0,09 mm; 0,35/0,2 mm è un candidato geometrico, non routing verificato. Vedere `bga-geometry-check.json` e `bga-footprint-repair.json`.

## Storage, firmware e display

La flash NOR selezionata è da 32 MiB. Non sono ancora provati boot ROM, loader, U-Boot, immagine Linux completa o aggiornamenti A/B entro questa capacità. `boot-software-check.json` registra fonti Rockchip, hash dei documenti e verifiche necessarie: il tool DDR usa MHz; il circuito senza pull-up DQSn richiede la famiglia DDRBIN regolare, non WDQS. Nessun loader è stato generato o caricato.

Il display IPS SPI da 0,96 pollici, 80×160, ha alimentazione a 3 V, buffer e comando retroilluminazione nello schema. La retroilluminazione usa ora 180 Ω in 0603: screening statico massimo 16,84 mA e 50,51 mW a 5,9 V, senza garanzia della piena luminosità. Il flex ha passo 0,7 mm: metodo di collegamento, assemblaggio, fissaggio e relazione interna VDD/VDDIO restano da chiarire. Non è stato inventato un connettore ZIF equivalente.

Restano inoltre aperti magnetiche Ethernet per l'esatto PHY/BSP, collegamento chassis/schermi, protezioni di sistema, capacità effettive dei condensatori e stabilità dei regolatori. La velocità VPN vicina al gigabit deve essere misurata su hardware, non si deduce dalle interfacce nominali.

## Costo e sourcing

Il subtotale dei candidati selezionati è **76,0362 USD**, con prezzi unitari osservati per riga: **341 posizioni con candidato selezionato, nessuna posizione attuale senza MPN, 14 piazzole di test**. Il completamento nominale non qualifica i componenti né esclude aggiunte necessarie alla revisione. Sono esclusi PCB, assemblaggio, attrezzaggi, scarti, materiale termico, involucro, trasporto e imposte. L'obiettivo di 50 EUR assemblati **non è raggiunto né dimostrato**.

I campi JLC di disponibilità ordinabile e stock visualizzato sono conservati separatamente; non sono una prenotazione o una conferma di disponibilità immediata per PCBA. Per la RAM sono stati osservati 19 chip: al massimo nove schede prima di riserva/scarti. Sono stati assegnati 71 resistori standard da 1% solo a richieste compatibili, escludendo quelle da 0,1%/25 ppm; la selezione non conclude la verifica termica o del circuito. Le alternative scaricate non si sommano automaticamente alla BOM. Capacità effettive, stato di produzione e footprint devono essere qualificati anche quando un componente è disponibile.

## Conferme tecniche esterne necessarie

`review/external-evidence-needed.json` contiene i quesiti precisi per fabbricante e produttori: montaggio flex e VDDIO del display, magnetiche Ethernet. Non è stato inviato alcun messaggio ai fornitori. Questi punti bloccano il rilascio; il file elenca separatamente anche il lavoro di progettazione ancora incompleto.

## Riproducibilità e limiti

`integrate_schematic.py` integra i fogli e annota i candidati dalla mappatura unica `sourcing/selected-references.json`. `check_integrated.py` confronta pin e percorsi DC: non verifica corrente, stabilità o sequenze temporali. I controlli specifici Wi-Fi, espansioni, reset e alimentazioni producono rapporti separati.

`build_floorplan.py` usa il Python KiCad e **ricrea una board senza piste**: non eseguirlo su un layout instradato. Gli script di schema richiedono `sexpdata`. Dopo ogni modifica rigenerare netlist, ERC, controlli pertinenti, floorplan/DRC se applicabile, release gate e inventario BOM.

Fonti primarie: documenti Rockchip, Hynix, TI e produttori dei componenti in `reference/`; [capacità JLCPCB](https://jlcpcb.com/capabilities/pcb-capabilities), [stackup JLCPCB](https://jlcpcb.com/impedance), [rkbin Rockchip](https://github.com/rockchip-linux/rkbin). URL e timestamp dei prezzi sono nei JSON di sourcing. Le verifiche documentali e numeriche non sostituiscono simulazioni SI/PI e collaudo fisico.

## Aggiornamento display e termica — 8 novembre

Il display è incluso nella versione base. Il collegamento rimovibile resta un obiettivo di montaggio/manutenzione; alimentazione, buffer e retroilluminazione restano sulla scheda principale. Il cavo USB-C rimane staccabile.

`check_passive_thermal.py` genera uno studio di sensibilità a convezione e irraggiamento, non una simulazione CFD né una previsione dei consumi Phoenix. Nell’ipotesi di involucro 90×40×20 mm, base e lati isotermi metallici, emissività 0,85, h=8 W/m²K e ambiente 40 °C, il modello smaltisce circa 1,9 W con superficie a 55 °C. Il limite di 55 °C è solo uno screening interno, non una certificazione. Gli scenari di potenza non sono misure: non è garantito che la forma proposta consenta raffreddamento passivo e VPN a piena velocità insieme.

Selezionati 95 candidati MLCC da 1/4,7/10/22 µF e aggiornate tre posizioni da 100 nF. I quattro nuovi MPN Samsung risultano in produzione e con quantità ordinabili JLC osservate; la capacità effettiva con tensione, temperatura e invecchiamento resta da verificare. Nessuna sostituzione X5R nelle posizioni che richiedono esplicitamente X7R.

### Verifica display e distinta — 8 novembre, continuazione

Il display rimane incluso. È stato esaminato il candidato N096-1608TBBIG09-C08 (C18723032), con FPC a 8 contatti da 0,5 mm. Non è ancora sostituito nello schema: il connettore HCTL C5213730 richiede contatti e rinforzo più lunghi; il Molex C293338 presenta differenze nelle tolleranze di larghezza e nella geometria dei conduttori. Il solo passo compatibile non basta. Evidenze e limiti sono in `review/display-connector-investigation.json`; serve anche adattare il driver LED, perché il nuovo pannello non espone LEDK.

Selezionati altri nove resistori da catalogo JLCPCB: tre da 200 kohm, due da 10 kohm con precisione 0,1%/25 ppm, uno da 120 ohm, uno da 51 kohm e due da 2,2 kohm. La selezione automatica controlla anche il valore resistivo dichiarato. La disponibilità osservata non equivale a prenotazione dei componenti né a qualificazione elettrica. Nessuna pista aggiunta in questa continuazione.

### Vincoli dei segnali veloci e piazzamento delle terminazioni

`tools/build_highspeed_plan.py` associa le prescrizioni Rockchip alle 40 reti reali che compongono quattro percorsi USB 3 (due direzioni e due orientamenti del connettore) e dodici percorsi RGMII. Il piano mantiene distinte le lunghezze dei percorsi completi dai singoli segmenti separati da resistenze, condensatori e multiplexer. Le larghezze delle piste e gli spazi delle coppie non sono ancora fissati: dipendono dallo stackup definitivo. Si veda `review/highspeed-routing-plan.json`.

Il generatore del piazzamento ora riserva prima le resistenze R501–R512 vicino alla rispettiva sorgente: RK3568 per TX, PHY per RX. La distanza geometrica massima pin–resistenza scende da 26,9564 a 6,3520 mm; il campo attuale è 1,6298–6,3520 mm. Queste sono distanze in linea retta, non lunghezze di piste né una verifica di integrità del segnale. Il controllo è riproducibile con `tools/check_rgmii_placement.py`; confronto e risultato sono nei report `rgmii-placement-before-source-targeting.json` e `rgmii-placement.json`.

Dopo la modifica: 353 footprint nel perimetro 90×40 mm, nessun fallimento del piazzamento automatico, DRC senza violazioni geometriche; restano 1.354 collegamenti del ratsnest e zero piste. Il display e la meccanica non sono inclusi nella verifica di ingombro. Altre 15 posizioni hanno ricevuto candidati di catalogo, con disponibilità JLCPCB osservata; restano da verificare capacità effettiva sotto tensione, tolleranze dei circuiti e taratura degli oscillatori.


### Revisione senza ventola e chiusura della selezione nominale

Il requisito passivo è registrato in `mechanical/passive-cooling-requirements.json`. Il percorso previsto è package del processore → interfaccia termica isolante e comprimibile → diffusore metallico → involucro. Display e flex devono avere supporto separato; non devono trasmettere il serraggio al processore o interrompere questo percorso. Non sono ancora definiti materiale acquistabile, carico di compressione, tolleranze e geometria finale.

`review/thermal-path-sizing.json` confronta un involucro ipotetico 100×46×24 mm, anche con fondo bloccato e superficie del display sottratta. Non modifica il PCB da90×40 mm e non dimostra il fit meccanico. A40°C ambiente, h ipotetico8 W/m²K e fondo bloccato, il modello smaltisce a55°C circa1,47 W con emissività0,1 o2,42 W con emissività0,85. 55°C resta uno screening interno, non una soglia normativa. Le potenze di scenario non sono consumi misurati. Il modello del TIM esclude le resistenze di contatto e non è una garanzia termica.

La verifica documentale del riferimento Henkel TGP3000 (3 W/mK) serve solo al modello: nessun MPN termico è approvato o aggiunto alla BOM, e non è stata verificata disponibilità JLC per questo materiale. La tabella termica Rockchip è stata controllata visivamente: è dichiarata dal produttore come simulazione di riferimento, non come qualifica del nostro involucro.

Eliminato R1701, duplicato della connessione di reset tramite R1507. La resistenza VBUS da900kΩ è ora costituita da R601/R605/R606, tre300kΩ0,1%25ppm in serie; controllo statico896,85–903,15kΩ nel campo termico di screening, entro880–910kΩ richiesti. Scelte precisioni e package disponibili anche per soglie USB e feedback Wi-Fi. Lo screening Wi-Fi comprende ora100ppm/K indipendenti nei due resistori: margine statico minimo circa139mV sopra3,2V dopo la perdita nominale ipotizzata sulla ferrite, prima degli altri effetti esclusi.

Aggiornati78 codici JLCPCB; tutti hanno quantità ordinabili pubbliche positive. `review/inventory-capacity.json` confronta quantità e fabbisogno per scheda: la RAM limita il conteggio nominale a9 schede prima degli scarti, senza prenotazione o conferma PCBA. La distinta resta una selezione di candidati.

Controlli aggiornati:1935 pin della gerarchia,110 del frontendUSB e204 della memoria senza differenze dai contratti; ERC0 errori e1 avviso USB_SHIELD;354 footprint, zero piste,1354 collegamenti del ratsnest. Non sono state risolte qualificazione del display, magnetiche Ethernet, routing, integrità dei segnali/alimentazioni o prove fisiche. Non sono stati prodotti file d'ordine.


### Decisione di configurazione — RAM confermata

Su indicazione dell’utente restano512MiB DDR3 e tutte le funzioni attuali, con raffreddamento passivo. La sola alternativa architetturale in valutazione è RK3562. `review/rk3562-migration-assessment.json` registra interfacce, risparmio del solo chip e verifiche necessarie. Il package misto0,5/0,65mm richiede una nuova analisi di escape: non è sostituibile nel footprint RK3568 e non è ancora dimostrato il risparmio netto sulla scheda assemblata. Nessuna sostituzione applicata allo schema.

### Alimentazione e masse del modulo Wi-Fi — 9 novembre

Collegati C2204 → FB2001 e FB2001 → U25.9, con bypass C2001/C2002 e tutti i 14 pad del modulo assegnati alla rete GND. C2001 è stato spostato da (34, 29) a (56, 21) mm sul fronte; nessun componente aggiunto o sostituito, quindi nessuna variazione della BOM. Il nuovo percorso prima della ferrite usa una dorsale In3.Cu da 1 mm con raccordi da 0,5 mm e coppie di vias 0,6/0,3 mm. Il lato modulo passa fronte/retro attraverso vias condivisi; le larghezze non costituiscono una qualifica della corrente.

`wifi-module-supply-validation.json` documenta il PCB finale e la prova negativa sul ramo VBAT. Il controllo `audit_rk3562_wifi_converter.py --require-local --require-module-supply --require-module-ground` verifica il rame salvato, inclusi i ritorni a massa. La rigenerazione include ora anche i tre nuovi stadi di routing.

Al termine di quella fase restavano da completare buck interno, VDDIO, clock, SDIO e RF del modulo; il buck interno è stato successivamente collegato come descritto sotto. Alcuni percorsi di massa arrivano a 4,1066 mm: continuità verificata, impedenza e prestazioni RF non qualificate. La scheda resta incompleta, con vincoli RK3562 ancora aperti; nessuna simulazione elettrica, prova fisica o approvazione alla produzione.

### Regolatore interno Wi-Fi — 9 novembre

L2001 e C2003 sono stati trasferiti sul retro, accanto al modulo: il ramo SW U25.21 → L2001.1 misura 2,6539 mm, largo 0,5 mm e senza vias. Collegati anche uscita e ritorno a massa del condensatore. Tre condensatori del processore ancora non collegati (C1607, C1625, C1619) sono stati riposizionati per liberare lo spazio: la loro posizione dovrà essere rivalutata durante il routing delle relative alimentazioni. Nessun MPN o valore è cambiato.

La rigenerazione completa supera DRC e controlli di continuità: **1313 segmenti, 136 vias, 1125 collegamenti ancora mancanti**, 1774 pad corrispondenti alla netlist. `wifi-module-buck-validation.json` contiene l’hash del PCB finale e i riferimenti alle verifiche. L’audit aggiunge `--require-module-buck`; `test_rk3562_wifi_buck_disconnect.py` elimina il rame SW su una copia e verifica che l’interruzione sia rilevata, lasciando validi uscita, bypass e masse.

Disponibilità JLCPCB rilevata il 9 novembre: L2001/C337891, 5260 unità ordinabili osservate a 0,1378 USD; C2003/C1779, 1558422 unità a 0,0342 USD. Quantità ordinabili e stock visualizzato sono registrati separatamente in `sourcing/wifi-module-buck-stock-refresh.json`; non sono una prenotazione né una conferma di disponibilità per assemblaggio. Subtotale dei due componenti a prezzi 1+: 0,1720 USD. La stima parzialmente aggiornata resta 67,4095 USD, esclusi PCB, assemblaggio, minimi di acquisto, scarti, spedizione, imposte e meccanica.

La continuità del buck non dimostra stabilità, ripple, margine di saturazione o comportamento termico. VDDIO, clock, SDIO, RF e molte altre reti restano incompleti. Nessuna prova fisica o simulazione elettrica eseguita; il blocco alla fabbricazione resta attivo.

### Clock lento Wi-Fi e prove VDDIO — 9 novembre

Integrati il segnale LPO a 32,768 kHz e il ritorno GND dell’oscillatore Y2001. R2003 è stata avvicinata all’uscita: da (30,5; 31) a (57,25; 22,5) mm, senza cambiare valore o MPN. Il tratto Y2001.3 → R2003.1 misura 2,5492 mm; dopo la resistenza il percorso comprende 0,8100 mm sul fronte, 22,3107 mm su In2.Cu e 3,6610 mm sul retro. Piste da 0,20 mm, vias da 0,45/0,20 mm. Sono collegamenti verificati geometricamente, non una qualifica del clock.

Rigenerazione completa e verifiche indipendenti superate: **1356 segmenti, 139 vias, 1122 collegamenti mancanti**, zero violazioni DRC geometriche e nessuna regressione delle continuità USB/Wi-Fi già richieste. `wifi-lpo-validation.json` identifica il PCB finale; la prova negativa interrompe il tratto In2 su una copia e l’audit rileva il guasto.

Le prove di avvicinamento del bypass VDDIO non sono state adottate: alcune disposizioni superavano il DRC ma impedivano il successivo routing del ritorno GND o del buck. Il PCB e il seed relativi a questi componenti sono stati ripristinati; i risultati e i prototipi sono separati in `migration-rk3562/experiments/wifi-vddio/` e `tools/experiments/`. Il prossimo riesame deve trattare insieme i pin U25.21/22/23, buck, bypass e ritorni, considerando anche i condensatori del SoC sul retro.

Il controllo distingue ora bypass VDDIO locale, collegamento al PMIC, segnale LPO e alimentazione dell’oscillatore. **VDDIO e alimentazione/bypass di Y2001 restano incompleti**: non è stato verificato un clock funzionante o un modulo operativo.

JLCPCB: Y2001/OVETDLJANF-32.768KHZ osservato ordinabile in 42 unità a 0,6183 USD; anche R2003 e C2007 risultano disponibili nell’osservazione registrata. Non è una prenotazione né una conferma di disponibilità per assemblaggio. La stima parzialmente aggiornata resta 67,4095 USD, escluse lavorazioni e meccanica; nessun componente aggiunto o sostituito. Nessuna simulazione elettrica o prova fisica eseguita.
