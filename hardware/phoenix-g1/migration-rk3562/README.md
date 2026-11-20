## Checkpoint corrente delle derivazioni di alimentazione

Il [PCB ricaricato](experiments/phy-power-parallel/layout-bank-feeds.json) comprende il ramo da 0,50 mm tra R8001.1 e R8006.2 su EMMC_IO_1V8 e 12 ulteriori collegamenti fra condensatori. Sono verificate 520 coppie. Restano 610 unioni minime su 213 reti. Il ritorno locale delle alimentazioni e la regolazione sotto carico restano da misurare.

## Checkpoint dei fissaggi USB-C

Sul [PCB verificato](experiments/phy-power-parallel/layout-usb-shell.json) i quattro terminali della schermatura di J1 formano un unico gruppo. Due tratti da 1 mm sono sul retro e il terzo è su In3.Cu. Le verifiche usano gli UUID dei quattro pad perché condividono tutti il numero SH. Restano 623 unioni minime su 213 reti. La terminazione dello schermo e la compatibilità elettromagnetica restano da qualificare.

## Checkpoint delle alimentazioni locali

Il [PCB verificato](experiments/phy-power-parallel/layout-peripheral-supply-balls.json) collega 27 coppie di sfere di alimentazione adiacenti e aggiunge 15 collegamenti locali tra condensatori. Le piste sono larghe 0,50 mm. La continuità di questi gruppi lascia ancora aperta la distribuzione dai regolatori. Restano 626 unioni minime su 214 reti e 123 segnalazioni di vie pendenti. Sono verificate 507 coppie sul PCB ricaricato.

## Checkpoint di alimentazione del PHY

Il [PCB ricaricato](experiments/phy-power-parallel/layout-phy-pin40-powered.json) collega C515, R530, C518 e U5.40. Il nuovo ramo su In2.Cu è largo 1,05 mm e lungo 5,719 mm. La deviazione di +5V_MAIN mantiene 0,80 mm su tutto il percorso sostituito. Due [prove di interruzione su copie del PCB](experiments/phy-power-parallel/phy-pin40-cut-tests.json) distinguono il tronco di distribuzione dalla via locale di C518. Sul PCB integro passano 465 verifiche di coppia. Restano 668 unioni minime su 214 reti. Le verifiche CAD non misurano ripple, stabilità del regolatore o avvio del quarzo.

## Checkpoint del pin 40 del PHY

Nel [PCB verificato](experiments/phy-power-parallel/layout-phy-pin40.json) C518 è sul retro. Il terminale di alimentazione raggiunge U5.40 con una via riempita e ricoperta. Il ritorno di C518 e quello del condensatore di carico C520 raggiungono la massa di C511. Il ramo C518–U5.40 deve ancora raggiungere il tronco +3V3_PHY. Restano 669 unioni minime su 215 reti. Le 464 verifiche di coppia includono i collegamenti del regolatore già validati. La geometria del ritorno e il circuito del quarzo richiedono verifica sul prototipo.

## Checkpoint dei ritorni BGA

Il [PCB verificato](experiments/phy-power-parallel/layout-outer-ground-mesh.json) include otto nuove vie di massa fuori piazzola e quattro rami sul SoC. Restano 670 unioni minime su 215 reti. Verificate 461 coppie sul PCB ricaricato, con 123 segnalazioni di vie pendenti.

## Checkpoint del SoC

Il [PCB con ritorni di massa del SoC](experiments/phy-power-parallel/layout-core-ground-mesh.json) aggiunge 13 vie passanti fuori piazzola (rame 0,45 mm, foro 0,20 mm) e 45 ulteriori rami verso la massa esistente. Le nuove vie sono distanti almeno 1 mm dai centri dei pad LPDDR4 vicini. Sono verificate 449 coppie sul PCB ricaricato. Restano 682 unioni minime su 215 reti e 123 segnalazioni di vie pendenti. Distribuzione della corrente, impedenza dei ritorni e producibilità del fanout richiedono ulteriori verifiche.

## Checkpoint dei ritorni di massa

Il [PCB ricaricato e verificato](experiments/phy-power-parallel/layout-all-ground-surface.json) include 15 nuovi rami di massa, dodici sul SoC e tre sui condensatori C1641, C1628 e C1636. Sono verificate 391 coppie. Restano 742 unioni minime su 215 reti e 123 segnalazioni di vie pendenti. La continuità in rame lascia da valutare impedenza e corrente dei ritorni condivisi.

## Checkpoint del tronco +3V3_PHY verso C516

Il [PCB verificato](experiments/phy-power-parallel/layout-phy-full-feed.json) collega R530 e C515 a C516 e U5.11. Il tronco su In2.Cu è lungo 8,817 mm e largo 1,05 mm. Due vie da 0,60/0,30 mm trasferiscono la corrente al lato componenti. Il ramo locale da C516 a U5.11 è lungo 1,248 mm. Le [cinque prove di interruzione](experiments/phy-power-parallel/phy-full-feed-proof.json) verificano il funzionamento delle vie in parallelo e la continuità del tronco anche isolandolo dal vecchio rame In2 della stessa rete.

La posizione del supporto ausiliario H8105 sul PCB corrente è **(70,20; 34,00) mm**. Il foro M2 da 2,20 mm e l’intera riserva meccanica sono traslati insieme di +0,20 mm lungo X. Le posizioni dei fissaggi della scheda figlia sono conservate. Per la staffa e il case usare le [coordinate dei cinque fori M2](experiments/phy-power-parallel/mounting-interface-current.json), confrontate con l’esportazione di foratura Excellon. C516 è a (66,90; 33,20) mm. Quote riferite alle coordinate KiCad.

Verificate 376 coppie sul PCB ricaricato. Rimangono 758 unioni minime su 215 reti e 123 avvisi di via pendente. La continuità CAD del nuovo ramo richiede ancora la verifica della caduta di tensione e della risposta ai transitori. Restano separati C518.1 e U5.40.

## Checkpoint del bypass LPDDR4

[PCB e audit cumulativo](experiments/phy-power-parallel/layout-opposite-bypass.json). C2308.1 raggiunge U2.F1 su +1V8_SYS con due tratti da 0,50 mm, lunghi complessivamente 1,563 mm, e una via da 0,60/0,30 mm. Le 374 verifiche di coppia sono passate sul PCB ricaricato. Restano almeno 759 unioni su 215 reti e 123 avvisi di via pendente. La ricerca di un ritorno aggiuntivo entro 1,20 mm dalla via di alimentazione non ha prodotto una geometria accettabile. Impedenza della distribuzione e risposta ai transitori restano da verificare.

### Vincoli verificati sullo stesso PCB

La [ricerca congiunta di C516 e del tronco da 1,05 mm](experiments/phy-power-parallel/phy-joint-pad-entry.json) include l’orientamento del condensatore, il suo ramo su U5.11 e le due coppie di vie di alimentazione esistenti. Nessun ingresso raggiunto nella finestra esplorata. Lo [spostamento di prova di H8105](experiments/phy-power-parallel/phy-bracket-trial.json) supera il DRC a +0,20 mm su X, ma non risolve il passaggio del tronco. Nel checkpoint del bypass LPDDR4 il foro conserva la posizione originale.

Su 64 segnali LPDDR4 aperti esaminati, [59 hanno una via collegata a entrambe le estremità](experiments/phy-power-parallel/ddr-reference-corridors.json). Cinque DQ mancano ancora della via dal lato SoC. Una [prova separata su In3](experiments/phy-power-parallel/ddr-byte-b1-maze-inner-all-data.json) collega tre segnali con verifica di continuità. Il controllo campiona il piano In4 lungo le piste, esclusi i primi e gli ultimi 0,60 mm. Impedenza, lunghezze interne ai package, temporizzazione del gruppo e ritorno alle transizioni restano aperti. Questo rame è salvato solo sulla copia di prova.

## Checkpoint dei ritorni dei package

[PCB e inventario](experiments/phy-power-parallel/layout-package-local.json). Rispetto al checkpoint R514, 34 unioni GND chiuse. Il CAD ricaricato conserva 373 verifiche di coppia, 215 reti con gruppi separati e 760 unioni residue. I sette nuovi fori sono esterni al rettangolo delle sfere con margine sul centro del foro di 0,35 mm. Tre sfere interne del SoC raggiungono vie già presenti. Restano aperti la verifica dei ritorni ad alta frequenza e il fanout dei segnali.

## Checkpoint dei ritorni sul rame esistente

[PCB ricaricato e verificato](experiments/phy-power-parallel/layout-ground-bends.json). Aggiunti 15 ritorni GND. Le 354 verifiche di coppia includono entrambi i pad di massa di J2001. Restano almeno 779 unioni su 215 reti e 123 avvisi di via pendente. Le prove di continuità non qualificano impedenza RF o induttanza di disaccoppiamento. Lo schema Ethernet con R514 da 1,5 kΩ è nel checkpoint precedente.

## Checkpoint R514

[PCB e foglio Ethernet](experiments/phy-power-parallel/layout-mdio-pullup.json). R514 da 1,5 kΩ, Yageo C114759. Netlist esportata e DRC verificati.

## Checkpoint corrente dei ritorni di massa

Il [PCB con l’audit cumulativo](experiments/phy-power-parallel/layout-peripheral-returns.json) aggiunge i ritorni al piano di J2001.2 e U23.3, lunghi rispettivamente 0,70 e 0,65 mm. Dopo la ricarica da disco risultano 339 verifiche di coppia superate e almeno 794 unioni residue su 215 reti. Rimangono 123 avvisi di via pendente. Il segnale RF di J2001 resta aperto.

La ricerca inversa del corridoio +3V3_PHY su griglia da 0,10 mm conserva C516 isolato dal tronco. La verifica documentale ha individuato una differenza indipendente sul bus di gestione Ethernet. R514 sul PCB vale 1,8 kΩ, mentre il datasheet RTL8211F rev. 1.9 prescrive 1,5 kΩ per MDIO. Il candidato 0402 da 1% è [Yageo RC0402FR-071K5L, C114759](https://jlcpcb.com/partdetail/YAGEO-RC0402FR071K5L/C114759). Il valore presente nel checkpoint resta 1,8 kΩ.

## Checkpoint corrente del regolatore PHY

Il [PCB verificato e l’inventario delle reti](experiments/phy-power-parallel/layout-regulator-joint.json) conservano le connessioni del checkpoint storage/I/O. Sul PCB ricaricato risultano 337 controlli di coppia superati, 215 reti ancora separate in più gruppi e almeno 796 unioni da completare. Il DRC cumulativo conserva i 123 avvisi di via pendente. Le 796 unioni sono una misura topologica distinta dagli avvisi.

C516 raggiunge U5.11 con un tratto da 1,04 mm. Sul ramo U5.30–L501.1 la lunghezza esposta prima del rame da 1,55 mm è 0,360 mm. Il detour da 1,55 mm su +1V0_PHY lascia spazio a una via GND da 0,55/0,30 mm nel pad esposto U5.41, salvata con riempimento e copertura. Restano da qualificare il processo di assemblaggio, la saldatura del pad e la dissipazione. Lo spostamento della via di ritorno accanto a C516 mantiene il ramo a 0,65 mm. La ricerca multistrato del collegamento da 1,05 mm tra il tronco +3V3_PHY e C516 rimane aperta. Gli esiti geometrici precedenti sono in [phy-c516-wide-ground-pad-entry.json](experiments/phy-power-parallel/phy-c516-wide-ground-pad-entry.json).

## Checkpoint del bus PMIC, dei controlli e della distribuzione eMMC

Il [checkpoint cumulativo](experiments/phy-power-parallel/layout-pmic-bus.json) include SCL tra U4.1 e R414.2 e SDA tra U4.2 e R415.2. Due prove di interruzione, in processi KiCad separati, rimuovono una via per ramo e verificano la perdita della sola continuità attesa rispetto ai controlli PHY. Restano aperti il collegamento dal SoC e la verifica dei tempi I²C. Sono inclusi sei tratti locali da 0,50 mm tra link e condensatori eMMC, senza qualifica della distribuzione completa né dei transitori.

## Checkpoint cumulativo dopo il routing dei ritorni e del reset

Il [PCB e il suo inventario di connettività](experiments/phy-power-parallel/layout-reset-connectivity.json) comprendono 42 ritorni di condensatori, la massa di R432 e il punto di prova TP1. R412 raggiunge C411 sul lato RESET_N e il gruppo di pull-up R416/R417 sul lato +3V3_PMU. La distribuzione a monte del gruppo è ancora aperta. Il conteggio delle unioni residue deriva dai gruppi di pad fisici ricalcolati sul PCB ricaricato.

## Ripresa della variante cumulativa PHY e memoria

Il [checkpoint del bus di gestione](experiments/phy-power-parallel/pmic-control-bus.json) identifica il PCB su disco. Comprende la riconciliazione dei fissaggi H8104/H8105 e del ritorno C1623, il reset LPDDR4, il collegamento locale di R201 e tre rami delle resistenze I²C. Gli otto collegamenti elencati in `held` restano aperti nella ricerca con componenti fissi. Il riferimento VDDQ di R201 e la distribuzione a monte dei pull-up richiedono ancora routing.

## Checkpoint della variante con punti di prova e polarizzazioni

La variante cumulativa verificata è identificata da [integrated-fixture-trunk.json](experiments/phy-power-parallel/integrated-fixture-trunk.json). Il file contiene il percorso relativo del PCB, SHA-256, 18 coppie di pad verificate, cinque prove di interruzione e le otto interferenze meccaniche residue. Il PCB principale conserva il proprio checkpoint separato.

Il controllo su disco preserva le 5.814 piste e vie e i 70 gruppi di pad del checkpoint C522. Tutte e cinque le resistenze di polarizzazione toccano il ramo +3V3_PHY e R521 raggiunge R510 sul lato RXD3. I restanti segnali e il bus RGMII completo richiedono ancora routing e verifica temporale. TP14, TP5 e TP9 raggiungono rispettivamente U17.4, C465.1 e U16.2. TP14 ha superficie di contatto libera dal foro di via. Il filtro C1503 e il partitore R1505/R1506 sono connessi localmente. Il ball U1.1P14 resta isolato. Lo schema porta al partitore +3V3_IO: prima di collegarlo al SoC occorre confermare la semantica di VBUSDET rispetto a inserzione USB e alimentazioni alternative.

I tentativi di escape non sovrapposti alle piazzole per i cinque bypass SoC interferenti sono registrati in [soc-bypass-escape.json](experiments/phy-power-parallel/soc-bypass-escape.json). Lo screening riguarda 13 ball, finestra ±1,2 mm, griglia 0,05 mm, traccia e clearance 0,20 mm, vie 0,45/0,20 mm. In tale finestra nessuna uscita rettilinea soddisfa i controlli. La qualifica del fanout BGA richiede il processo PCB e la geometria appropriati.

## Variante PHY verificata in CAD — 19 novembre 2026

La variante più avanzata della revisione congiunta di L501 e dei bypass PHY è identificata da [c522-verified.json](experiments/phy-power-parallel/c522-verified.json). Le modifiche restano nello studio isolato. Il [checkpoint di ingresso](experiments/phy-power-parallel/phy-upstream-verified.json) copre R530–C515 e le sue due coppie di vie. Il checkpoint successivo aggiunge la distribuzione a C522, il pin 38 e il ritorno a massa. Le prove di rimozione delle vie sono state eseguite su copie in memoria del PCB ricaricato da disco.

Il percorso a monte da 1,05 mm comprende 27,44 mm su In2. Il ramo a valle da 1,55 mm misura 5,40 mm, con ritorno di C522 da 3,43 mm. La modifica al quarzo porta XIN da 8,83 a 9,98 mm. Restano da qualificare il comportamento del convertitore, il fanout locale, il quarzo e l'assemblaggio delle vie in prossimità delle piazzole. I conteggi del checkpoint principale seguente si riferiscono al PCB principale.

## Salvataggio parziale — 17 novembre 2026, RXCLK e corridoi PHY

Checkpoint principale: `bdeb44f58dea3d0261469c1d3f7eeb5a9e6df03e95648710393c9e09c83f6aeb`.
RXCLK: R512/R522 sul retro, ramo di bias da 1,374 mm e massa ripristinata.
Ricostruzione completa superata: **195 coppie, 67 test CAD**, 23 stadi.
Restano 226 reti multipad aperte e 951 unioni topologiche minime.
Nessuna qualifica elettrica o di produzione.

Variante separata: `phy-compact-inductor/corridor/checkpoint.json`:
C517 riposizionato, ramo di ingresso da 1,05 mm, ritorni C511/C515 da 0,50 mm,
secondo via GND C511 e bias RXCLK. Ricostruzione transazionale e 7 test
isolati superati. Non adottata nella BOM o nel PCB principale.
Riprodurre con Python KiCad 10 e `tools/rebuild_phy_corridor_study.py`
sotto `hardware/phoenix-g1/`.

Ultima prova `corridor/switch-fanout-probe.json` RESPINTA dal DRC, non
adottata. Il tratto di uscita dal pin proposto è anche più stretto della
raccomandazione storica Realtek: nessuna deroga approvata. Restano aperti
nodo SW, alimentazione a monte, distribuzione 1 V e qualifiche SI/PI/termiche.
Le sezioni successive sono storico e possono contenere conteggi superati.

## Reset PHY integrato e variante compatta — 17 novembre 2026

Checkpoint autorevole (percorso dalla root):
`hardware/phoenix-g1/migration-rk3562/experiments/pmic-ldo-inputs/working-candidate.json`, SHA
`96b01d90aa6225a873dac818f007459245adeb207920009b7f11e223b8266394`. Collegato U5.12 a R515.2 sul fronte,
0,20 mm, 6,748 mm, senza via. Ricostruzione completa dei 23 stadi superata:
194 coppie, 65 test CAD, test corto XIN/5V, rilevamento meccanico e rollback.
Restano 226 reti multipad aperte e 952 unioni topologiche minime;
19 possibili conflitti meccanici preesistenti. Nessuna qualifica elettrica.

La revisione congiunta è descritta in
`hardware/phoenix-g1/migration-rk3562/experiments/phy-compact-inductor/README.md`:
induttore 2,5×2 mm, C511/C515 0603 e corridoi GND ripristinati mantenendo
le larghezze originali. Ramo L501.2–C511.1 da 1,55 mm sul fronte senza via,
2,511 mm, verificato con DRC, preservazione e cinque test dedicati.
Variante sperimentale separata, NON adottata nella BOM né nel PCB autorevole.
Il regolatore richiede ancora ingresso, nodo SW e distribuzione ai carichi;
restano da qualificare DCR/ripple, capacità effettiva, stabilità e termica.
La disponibilità JLC osservata è presale/overseas, non allocazione PCBA.

Le sezioni seguenti sono storico e possono riportare conteggi superati.

## Checkpoint induttore PHY sul fronte — 17 novembre 2026

Ripartire da `migration-rk3562/experiments/pmic-ldo-inputs/working-candidate.json`
(`working-candidate.json` nella directory dello studio).
PCB finale: `pcb/ethernet-dvdd33-bypass.kicad_pcb`.

L501 sul fronte a (57,4; 30,8) mm, ruotata 180°; Y501 a (57,75; 34,8) mm.
C1014 è sul retro a (62; 36) mm; U23 sul retro a (75,5; 25,5) mm.
Questi due componenti erano privi di piste collegate. Conservati pin/net,
connessioni precedenti e bypass PHY. Nessun componente o valore aggiunto.

XIN attraversa il retro con due via 0,45/0,20 mm; XOUT resta sul fronte.
Per evitare un corto con il via XIN, un segmento +5V_MAIN su In2 da 0,8 mm
è sostituito da tre segmenti della stessa larghezza: 8,78 mm contro 8,45 mm.
La sostituzione è esplicita nella prova di preservazione dello stadio clock.
Nessuna regola di clearance o larghezza minima allentata.

Ricostruzione completa di 23 stadi superata: **193 coppie, 64 test CAD**,
più test del corto XIN/5V, rilevamento meccanico e rollback.
Il test del corto rimette il vecchio segmento su una copia e verifica il
corto preciso fra la pista a 5V e il via XIN; il checkpoint resta invariato.
L'audit rifiuta L501 sul retro. Nessuna nuova violazione DRC o interferenza;
restano 19 possibili conflitti meccanici preesistenti.

**Non è una qualifica del convertitore o dell'oscillatore.** Restano aperti
commutazione, alimentazioni principali, ritorni, stabilità e corrente.
Le lunghezze aggregate di rame del clock sono circa 8,83 mm per XIN e
10,40 mm per XOUT, includendo i rami dei condensatori; non includono
la lunghezza verticale dei via e non sono una verifica SI.
Parassiti e accoppiamento al futuro percorso SW richiedono revisione e prove.
U23 sul retro richiede ancora il progetto dei percorsi ESD, C1014 quello
del disaccoppiamento CPU. `pcb/phy-regulator-layout-review.json` aggiornato.

Attività successive già esaminate: `probe_phy_bulk_placement.py` non trova
una posizione frontale isolata per C511 nel campo provato; trova 16
possibilità per C515, ancora senza percorso di potenza verificato.
`report_current_rgmii_placement.py` usa il checkpoint RK3562 corrente:
terminazioni TX a 3,01–5,32 mm dalla sorgente, RX a 1,63–3,87 mm.
Sono distanze in linea retta, non lunghezze instradate o risultati di timing.
Tutti i 12 resistori hanno zero piste collegate: una revisione congiunta
con il percorso di potenza è possibile, ma non ancora adottata.

I vecchi studi isolati sono storici e conservano gli hash della rispettiva
prova. Il generatore precedente del clock è in `probe-inputs/`; le prove
isolate copiano ora anche le librerie footprint per evitare DRC spurii.
Rigenerare con Python KiCad e `hardware/phoenix-g1/tools/rebuild_local_copper.py`.

227 reti multi-pad ancora aperte, 953 giunzioni topologiche minime:
non sono un conteggio di piste o una percentuale. PCB 90×40 mm, target
85×35 non qualificato; 13 pad display assenti. Nessuna prova fisica,
ordine, commit/push o modifica ROCK/software. Nessun nuovo MPN o prezzo
verificato. Le sezioni seguenti sono storico.

## Checkpoint bypass Ethernet — 17 novembre 2026

Fonte corrente: `migration-rk3562/experiments/pmic-ldo-inputs/working-candidate.json`
(dalla directory dello studio: `working-candidate.json`).
PCB `pcb/ethernet-dvdd33-bypass.kicad_pcb`.
Cinque condensatori riposizionati e collegati ai rispettivi pin PHY:
C514→U5.21, C516→U5.11, C512→U5.3, C517→U5.28, C519→U5.29.
Ristabilite tutte le loro masse; raccordati U5.28/29. Nessun nuovo MPN.

Audit cumulativo di **193 coppie**, **63 test CAD passati**, ricostruzione completa
di **23 stadi** dopo five-volt-testpoint riuscita. Nessuna nuova violazione DRC
o interferenza meccanica; restano 19 possibili interferenze preesistenti.
Le nuove diramazioni sono larghe 0,20 mm e misurano circa 1,53–4,11 mm;
non sono una qualifica di corrente o disaccoppiamento. Le tre uscite dei pin
ravvicinati usano un tratto rettilineo esplicito da 0,80 mm senza ridurre
larghezze/clearance. I test di guasto isolano anche percorsi alternativi.

Inventario: 227 reti multi-pad aperte; **953 giunzioni topologiche minime**
fra gruppi ancora separati. Non sono 953 piste, né una percentuale di completamento.
Conservati clock, fissaggi e connessioni precedenti. Display: 13 pad ancora assenti.

Revisione del convertitore: `pcb/phy-regulator-layout-review.json`.
La rev. 1.1 Realtek reperita su Boardcon esplicita induttore/bulk sul fronte,
tratti di potenza larghi e senza via nei percorsi indicati. È precedente alla
rev. 1.2 locale: evidenza conservativa, da riconciliare con la guida corrente.
**L501 sul retro resta provvisoria e non approvata**; i nuovi rami da 0,20 mm
non sostituiscono dorsali di potenza dimensionate. C511/C515 restano da riavvicinare.

`probe_phy_inductor_front.py` non trova un piazzamento isolato nel campo
esaminato: gli esempi meno congestionati interferiscono con C520/Y501.
`probe_phy_clock_inductor_joint.py` prova sei disposizioni in una copia temporanea,
senza modificare il checkpoint: nessuna conclude il piazzamento locale dei due
condensatori del quarzo. Rapporti `phy-inductor-front-probe.json` e
`phy-clock-inductor-joint-probe.json`. Non è una prova di impossibilità.
I tentativi C513/C518/C522 non sono promossi; servono un riassetto congiunto
più ampio e la revisione del percorso di potenza, non altre piste isolate.

Rigenerazione: Python KiCad con `tools/rebuild_local_copper.py` nella cartella hardware.
Audit distanze/assegnazioni: `tools/report_phy_supply_placement.py`.
I report di tentativi precedenti mantengono gli hash della rispettiva prova;
non sono checkpoint alternativi utilizzabili. Nessun aggiornamento dei prezzi:
nessun nuovo componente scelto, nessuna dichiarazione di stock corrente.

Nessun ordine, commit/push o modifica software/ROCK. PCB ancora 90×40 mm,
obiettivo 85×35 mm non qualificato. Alimentazioni, SI/PI, termica passiva,
avvio, EMC/DFM e prove fisiche restano aperti. Le sezioni seguenti sono storiche.

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

## Active memory direction — 2026-11-10

User approved migration toward **1 GB LPDDR4 in one package**, compact layout, non-touch display and board-mounted five-way control. Qualification work is in `experiments/lpddr4-1gb/`. Active CAD remains DDR3 until the new memory electrical map, power and boot requirements are qualified. This supersedes the DDR3 direction as a target, not as a claim of completed CAD migration.


### Joint Wi-Fi power candidate — 2026-11-09

`experiments/wifi-vddio/joint-placement/final.kicad_pcb` is a separate candidate, not the accepted PCB or the transactional rebuild output. It passes geometric DRC and the independent Wi-Fi continuity audit including local VDDIO bypass, module grounds, internal buck and LPO. A negative test removes the 12 VDDIO back tracks and detects the intended disconnection without losing other module checks.

This resolves the previous bounded-routing failures by repositioning the buck/capacitor group, using an internal-layer buck output bridge and allowing a 7.3024 mm U25.20 ground path. The output bridge is approximately 11.516 mm; both paths require electrical layout review before adoption. Upstream PMIC and oscillator power are still incomplete. Displaced SoC decoupling also remains unqualified. No simulation or physical verification was performed; no fabrication release. The main PCB and its accepted reports are unchanged. See the candidate `result.json` for hashes and evidence.

### Oscillator supply candidate — 2026-11-09

`experiments/wifi-vddio/oscillator/candidate.kicad_pcb` extends the joint candidate with C2007 on the front at (52,28), local oscillator bypass and a connection to the module IO rail. DRC reports zero geometric violations; independent continuity and a deliberately disconnected feed test pass. Front copper was visually inspected. PMIC power remains absent, so this is not an operational clock/Wi-Fi result.

U4.55 escape is incompatible with the current generic 0.20 mm track/0.20 mm clearance recipe: adjacent 0.15 mm pads on 0.35 mm pitch leave 0.175 mm clearance around a centered 0.20 mm trace. A qualified fine-pitch power escape is needed, not a global relaxation of DRC. Source reservoir placement, current capacity and sequencing remain open. Main PCB and accepted reports remain unchanged.
