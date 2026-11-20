# Audit indipendente eMMC / boot — 18 novembre 2026

Stato: pin mapping verificato documentalmente; avvio e sequenze NON qualificati. Nessuna modifica CAD, BOM, firmware o registri del dispositivo. La memoria flash è presente nello schema: U8001 Samsung KLM8G1GETF-B041, 8 GB eMMC, non una microSD obbligatoria.

## Evidenze riproducibili

`parallel_boot_audit.py` legge la netlist integrata esportata nuovamente con KiCad CLI (`sources/current-integrated.xml`). `pin-audit.json` contiene 45 confronti dei ball Samsung/RK3562 e 13 RFU isolati: tutti passano. La mappa attesa è trascritta dal datasheet Samsung rev1.21 tabella 2, non ricavata dal generatore dello schema. Non verifica lunghezze, impedenze, saldabilità o boot ROM.

Fonti primarie locali: `hardware/phoenix-g1/reference/samsung-klm8g1getf-b041.pdf`, `rk3562-datasheet-v2.1.pdf`; reference progettuale `rk3562-oomwoo-reference.pdf`, pagina PDF 14 ispezionata visivamente. Fonte software: `sources/pwrseq_emmc.c` e `mmc-pwrseq-emmc.yaml`, scaricate dal repository ufficiale torvalds/linux (master, snapshot locale con hash; non necessariamente versione kernel del prodotto).

## Matrice di verifica

| Sottoblocco | Evidenza effettiva | Esito / azione |
|---|---|---|
| Bus x8 | DAT0..7, CMD, CLK, STRB corrispondono ai ball di entrambi i componenti | PASS pin mapping. Le vecchie label FSPI di alcuni pin del simbolo non alterano le net, ma confondono la lettura. |
| I/O | U1.1F14 VCCIO2 e tutti i VCCQ eMMC su EMMC_IO_1V8 | PASS dominio nominale; validare rail entro **1,70..1,95 V**, intervallo Samsung più stretto del limite GPIO RK3562. |
| VCC | Quattro ball VCC su EMMC_3V3, tramite R8007 a +3V3_IO | PASS nominale 2,7..3,6 V; verificare transitori e carichi condivisi. |
| VDDI | C2 con solo C8001 2,2 µF verso massa | PASS isolamento nodo interno: non aggiungere alimentazione né carichi. Capacità effettiva/part number restano da qualificare. |
| DAT/CMD pull-up | DAT0 e CMD 10k; DAT1..7 senza resistenze esterne | Coerente reference. Samsung descrive pull-up interni DAT1..7; non dichiarare automaticamente mancanti le sette resistenze. Pinmux e lifecycle pull-up host da verificare. |
| STRB | R8005 47k a massa | Dentro intervallo Samsung 10..100k HS400. Il reference mostra questa resistenza NC: differenza consapevole, non errore dimostrato. |
| CLK | R8004 22 Ω serie | Valore reference iniziale, non prova di signal integrity HS200/400. |
| Reset | K5 e R8003 10k soltanto | Nessun driver reset runtime. Il reference ha anch'esso nessun driver runtime, ma aggiunge C4010 100n. Vedere sotto. |
| Assorbimento | Samsung tabella32: 180mA VCCQ, 50mA VCC per 8GB HS400 | Sono RMS su finestra 100ms; non usarli come limite del picco istantaneo. Budget PMIC deve includere memoria + DDR/WiFi/IO condivisi. |
| RFU | 13 ball non collegati | PASS; non riutilizzare per fanout/alimentazione. |

## Reset: scelta concreta e limiti

**Mantenere l'architettura reference senza introdurre ora un nuovo GPIO/buffer.** Non esiste un requisito stabilito di reset hardware indipendente; la sua assenza non dimostra che il warm boot fallisca. Il reference Oomwoo non fornisce un reset eMMC comandabile: R4002 10k verso VCCIO_FLASH e C4010 100n verso GND generano soltanto un ritardo iniziale.

Differenza reale: Phoenix non ha il condensatore 100n sul reset. La costante RC del reference è circa 1ms (10k × 100n); il tempo di attraversamento della soglia dipende da soglia, tolleranze, rampa della rail e scarica residua. Questo RC **non è un supervisore di tensione, non prova un impulso valido durante brownout e non genera un reset a ogni reboot**. Non aggiungerlo automaticamente come soluzione al warm boot. Per una copia rigorosa del reference può essere predisposto un condensatore 100n DNP, dopo aver verificato soglie e timing del componente reale; nessun CAD è stato cambiato qui.

Samsung EXT_CSD[162] `RST_n_FUNCTION` ha default 0x00: il pin hardware reset non è abilitato nello stato iniziale documentato. L'eventuale abilitazione permanente richiede una procedura produttiva esplicita; non trattarla come normale configurazione runtime reversibile. Non sono stati scritti registri, fuse o EXT_CSD.

Linux `mmc-pwrseq-emmc` dispone di un GPIO reset e registra un restart handler anche per emergency_reboot quando il GPIO non richiede sleep. La sua semplice presenza nel device tree **non può creare un collegamento fisico assente**. Nel progetto corrente non dichiarare `reset-gpios` fittizio. Questo driver non garantisce comunque un reset su perdita alimentazione o watchdog che bypassa il software.

Test necessari, separati: cold boot; reboot Linux pulito dopo accessi; riavvio watchdog senza shutdown; recovery dopo brownout; boot dopo interruzione di scrittura. Verificare effettive sequenze BootROM/U-Boot, modalità bus lasciata alla memoria, power-off notification e consistenza filesystem. Un riavvio software non equivale a togliere entrambe le alimentazioni eMMC.

Le rail non sono indipendenti: R8006 lega VCCQ a +1V8_SYS, condivisa con LPDDR4; R8007 lega VCC a +3V3_IO, condivisa con WiFi/IO. Non spegnere tali rail per simulare un power-cycle solo eMMC: sarebbe un cambiamento del sistema e può introdurre retroalimentazione attraverso I/O. Un eventuale reset indipendente futuro richiederebbe GPIO a livelli compatibili, buffer open-drain e verifica boot pinmux, oltre alla policy EXT_CSD; non selezionato né necessario per questa revisione.

## Acquisto: verifica pubblica, non allocazione

Snapshot JLC `sources/C499918.json`, 18 novembre 2026 09:02 UTC: KLM8G1GETF-B041 C499918, prezzo iniziale pubblico USD17,775; presale394, overseas456, `assemblyComponentFlag=false`. **Non prova disponibilità immediata per assemblaggio PCBA**. Nessun ordine/preventivo avviato.

## Qualificazione residua concreta

Il rail eMMC deve essere verificato con minimo1,70V anche durante trasferimenti e con tutti i carichi condivisi; il range più ampio del SoC non basta. Le capacità indicate nello schema sono ancora candidate, quindi il valore nominale non certifica il decoupling effettivo. La memoria supporta HS400 ma il pin mapping non qualifica tale modalità: avvio a modalità conservativa e aumento dopo verifica SI e test hardware. La flash richiesta è quindi progettata e cablata logicamente, non ancora provata fisicamente.

## Addendum: confronto net PCB

`board-net-audit.json` confronta 187 pad eMMC/passivi nel checkpoint PCB: nessuna differenza sulle net collegate. 120 pad NC/RFU hanno net vuota sul PCB e nomi `unconnected-*` nella netlist: sono differenze di rappresentazione, non connessioni mancanti. Non equivale a verifica di piste completate.

## Addendum: RK809 VDC pin 61 e neck locale

Fonte: RK809 rev2.3 (`reference/RK809-5-C2939628.pdf`), p19 descrizione pin61 e p29 sequenza. VDC è ingresso di rilevazione tramite partitore: soglia prima salita 0,55V, attesa documentata140ms. Non è ingresso di corrente del convertitore. Il datasheet consultato non fornisce un limite numerico dedicato di leakage VDC: non inventarne uno.

Netlist: R410180k da **+3V3_SYS**, R411100k a GND, C410100n, U4.61. Valore nominale1,179V; impedenza Thevenin64,286kΩ; costanteRC6,429ms. Per gradino ideale3,3V, attraversamento0,55V dopo circa4,04ms, distinto dai140ms di qualificazione interna. La rampa reale e le tolleranze richiedono verifica di sequenza; non usare questo calcolo per certificare l'avvio.

La corrente nel ramo superiore, persino con nodo a0V e sorgente3,3V, è limitata da180k a18,3µA: non c'è una ragione di portata per imporre0,20mm al breve ingresso VDC. Come esempio dimensionale, rame35µm, lunghezza1mm e larghezza0,15mm danno circa3,28mΩ a20°C. È trascurabile rispetto al partitore; anche aumenti termici/tolleranze di rame non ne fanno un rail di potenza. C410 deve restare sul nodo filtrato, vicino all'ingresso; evitare accoppiamento dai nodi SW e conservare ritorno GND corto.

Geometria proposta esclusivamente documentale: uscita dal pad61 allineata al centro, larghezza0,15mm entro il fanout QFN; poi0,20mm appena fuori dall'inviluppo dei pad adiacenti. Con passo0,35 e pad adiacente0,15, la distanza bordo-bordo nominale è0,200mm per traccia0,15; traccia0,20 scende a0,175mm. Quindi la traccia più larga viola il margine locale mentre0,15 mantiene esattamente0,20. Non ridurre clearance né allargare pad per aggirare DRC. Il punto di espansione a0,20 deve essere verificato geometricamente e non deciso solo dal bordo del corpo QFN; questo esempio non autorizza automaticamente un percorso specifico.

JLCPCB capacità ufficiali consultate il18nov2026: https://jlcpcb.com/capabilities/Capabilities?type=1 e https://jlcpcb.com/help/article/jlcpcb-copper-weight . Con rame1oz, min width/space0,10/0,10mm per1–2layer e0,09/0,09mm multistrato. Una traccia0,15 con clearance0,20 rientra quindi nelle capacità pubblicate **per quel rame**; confermare lo stackup effettivo, non estendere a2oz. Questa è una giustificazione elettrica e di fabbricazione per una regola specifica del solo collo VDC, non una riduzione della clearance o della larghezza dei rail PMIC. Nessuna regola CAD è stata modificata.

Calcoli riproducibili e ipotesi salvati in `vdc-neck-calculation.json`. Il collo non risolve da solo ostacoli C425/+1V8_SYS, vias e rame su altri layer: quelli restano compito della revisione geometrica congiunta.

## Addendum: U4 land pattern, C425 e stencil

Ispezione visiva RK809 rev2.3 p17–18: QFN68 corpo7×7mm, pitch0,35; terminale b0,10..0,20 (nom0,15), L0,30..0,50 (nom0,40); EP5,39..5,59 (nom5,49). Nel PCB U4: land0,74×0,15, centri a±3,41; EP5,5×5,5. Numerazione top-view coerente: 1alto-sinistra,17basso-sinistra,18inizio lato basso,34fine lato basso,35lato destro basso,51alto-destra,52alto-destra,68alto-sinistra. Pin61 su lato alto. Nessuna inversione riscontrata. Il datasheet dà dimensioni package, NON una land pattern assemblaggio qualificata: larghezza land0,15 coincide con terminale nominale ma è inferiore al massimo0,20; non trasformare il confronto dimensionale in approvazione di processo. Non allargare i land senza riesaminare clearance/fanout.

C425 è input bulk su+3V3_SYS/GND, non output +1V8_SYS. MPN CL21A226MOCLRNC corrisponde a22µF **16V** X5R±20%0805; la label schema22u/10V è inesatta e va corretta nella futura sincronizzazione BOM, senza cambiare componente. Fonte primaria https://product.samsungsem.com/mlcc/CL21A226MOCLRN.do ; HTML e curva numerica archiviati. A3,3V la curva tipica dà12,245µF; a1,8V17,376µF (25°C,120Hz,0,5Vrms). Non sono minimi garantiti e non includono tolleranza/temperatura/invecchiamento. Per la revisione geometrica mantenere corto il percorso di ingresso e ritornoGND, non solo la connessione nominale.

`parallel_boot_thermal_audit.py` produce `thermal-pad-audit.json`. U4 EP69 espone F.Paste su30,25mm² senza override locale e contiene9fori0,3mm: potenziale wicking/voiding da trattare nel processo. Altri pad ampi con paste: U5.41 3,6×3,6; U24.21 1,6×2,6; U17.17 eU26.17 1,6×1,6. Non tutti richiedono automaticamente la stessa riduzione: servono rispettivi datasheet e Gerber finali. U6 ha già aperture separate1,39×1,13, quindi non è lo stesso caso.

Fonte primaria di metodo, non specifica Rockchip: TI `QFN and SON PCB Attachment`, SLUA271C, https://www.ti.com/lit/an/slua271c/slua271c.pdf . Raccomanda tipicamente50–70% copertura pasta del thermal pad; ADI guida QFN https://www.analog.com/en/resources/app-notes/smt-assembly-and-pcb-design-guidelines-for-maxims-standard-wirebonded-quad-flatpack.html descrive50–80% e area ratio>0,66.

**Proposta da verificare, NON applicata:** U4 9finestre quadrate1,45×1,45mm, centri x/y=-1,70,0,+1,70 rispettoEP. Area18,9225mm², copertura62,55%, separazione0,25mm, bordo esterno0,325mm. Con stencil0,10mm l'area ratio della singola apertura quadrata è3,625; volume teorico pasta1,892mm³. Ciò non determina altezza finale solder né garantisce voiding. Alcune finestre sovrappongono i fori esistenti: **questa proposta presuppone vias riempite e planarizzate con processo approvato**, non semplicemente lasciate aperte. Se i fori restano aperti occorre ridisegnare finestre rispetto ai fori o concordare soluzione di processo; non applicare questo pattern in automatico. Tenting inferiore non equivale a riempimento e può intrappolare gas. Il vincolo da chiudere è stencil/viafill specifico PMIC, non routing.
