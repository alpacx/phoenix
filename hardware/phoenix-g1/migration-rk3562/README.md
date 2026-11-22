## Condensatore sull’uscita analogica da 1,8 V del PMIC

Il checkpoint adottato è `experiments/phy-power-parallel/layout-pmic-image-c468.json`. Restano 399 unioni su 200 reti. C468 da 1 µF raggiunge U4.6 sulla faccia superiore attraverso 2,494 mm di rame. Il tratto sulla piazzola è largo 0,20 mm e lungo 0,304 mm. Il resto è largo 0,30 mm. Il ritorno GND misura 0,598 mm fino al foro già collegato al piano. C421 è stato traslato di 0,20 mm e mantiene ciascuno dei sei contatti diretti precedenti. Il controllo sui bordi e sul centro delle piste conferma che il piano di riferimento è continuo.

L’inventario indipendente sul PCB ricaricato coincide con il checkpoint. Le 768 coppie sono collegate, il DRC comparativo e il controllo degli ingombri non rilevano regressioni. Il collegamento dell’uscita ai carichi del SoC, la verifica dell’anello di regolazione e le misure fisiche restano aperti.

## Bypass da 1 µF sul banco I/O a 3,3 V

Il checkpoint adottato è `experiments/phy-power-parallel/layout-io-c1628-local.json`. Restano 400 unioni su 200 reti. C1628 raggiunge il banco di distribuzione con 0,72 mm di pista larga 0,50 mm. La sfera SoC a 3,3 V più vicina dista 1,703 mm contro i 6,973 mm precedenti. Il gruppo di distribuzione resta separato dalle sfere del SoC. Tutte le 766 coppie verificate e il rame precedente sono conservati. I due raccordi sul retro hanno riferimento continuo sul piano GND adiacente nei 264 campioni verificati.

Il percorso geometrico stimato dal terminale di massa al primo foro connesso al piano passa da 1,564 a 1,678 mm. L'aumento di 0,114 mm accompagna il collegamento del terminale positivo prima isolato e l'avvicinamento al carico. L'impedenza effettiva resta da qualificare. L'inventario indipendente sul PCB ricaricato coincide con il checkpoint. Il confronto DRC non introduce nuove violazioni.

## Bypass da 100 nF per VDD1 della LPDDR4

Il checkpoint adottato è `experiments/phy-power-parallel/layout-ddr1-c2303-local.json`. Restano 401 unioni. C2303 raggiunge il gruppo da 1,8 V già collegato a U2.F1. Il ramo positivo da 0,50 mm termina sul rame esistente a 0,054 mm dal centro della piazzola. Il ritorno da 0,721 mm raggiunge una via di massa con foro da 0,30 mm. Il centro del condensatore passa da 2,967 a 2,025 mm dalla sfera VDD1 più vicina. Sul file ricaricato risultano verificati il riferimento sotto entrambi i raccordi, tutti i gruppi precedenti e 764 coppie di piazzole. Le altre sette sfere VDD1 della memoria restano separate dal banco.

## Banco di bypass GPU

Il PCB adottato è `experiments/phy-power-parallel/layout-gpu-c1617-bypass.json`. Restano 402 unioni. C1617 da 4,7 µF raggiunge il gruppo C1619–C1620 tramite 1,720 mm di rame da 0,80 mm. Il ritorno alla via di massa misura 1,586 mm contro i precedenti 3,302 mm. La distanza tra il centro del condensatore e la sfera GPU più vicina scende da 11,150 a 9,909 mm. Sul PCB ricaricato sono verificati i gruppi pregressi, 762 coppie di piazzole e il piano di riferimento sotto entrambi i raccordi. Sono ancora aperti il collegamento del banco al carico e la qualifica della distribuzione di alimentazione.

## Bypass VCCIO_ACODEC

Il checkpoint adottato è `experiments/phy-power-parallel/layout-codec-bypass-exposed.json`. Restano 403 unioni su 200 reti aperte. Il condensatore C463 da 1 µF raggiunge U4.28 con 0,591 mm sul fronte, una via e 1,575 mm sul retro. Il ritorno da 1,354 mm termina direttamente su uno dei nove fori metallizzati da 0,30 mm del pad esposto U4.69. Il ricollocamento adiacente conserva entrambi i raccordi di C482. Il percorso da 0,60 mm dell'alimentazione a 3,3 V su In4 misura ora 4,880 mm. Nel confronto locale dei piani, 41 campioni su piste di massa perdono la copertura della massa adiacente; tutti i campioni precedentemente coperti sulle piste di segnale e alimentazione restano coperti. Il DRC ricaricato conserva i risultati precedenti e 760 coppie di piazzole risultano connesse. L’impedenza del bypass e la risposta ai transitori richiedono ancora qualifica elettrica.

## TXD3 e percorso del reset

Il checkpoint adottato è `experiments/phy-power-parallel/layout-rgmii-txd3-reset-referenced.json`. Restano 404 unioni. U1.AB2 raggiunge R504.1 con 2,897 mm sul fronte. Il reset usa due vie esistenti e 28,756 mm su In3. La verifica a PCB ricaricato conserva 758 coppie e tutti i gruppi di piazzole preesistenti, con zero nuove segnalazioni DRC. Il riferimento di massa del reset sulle sezioni piane è stato campionato fino ai due antipad. La continuità delle sezioni complete RGMII verso il PHY e l'effetto elettrico della nuova lunghezza di reset richiedono ancora verifica.

## Ritorni condivisi sotto i BGA

## Clock TX del bus RGMII

Il PCB corrente è `experiments/phy-power-parallel/layout-rgmii-short-source-clock.json`, con 405 unioni aperte. La sfera U1.Y2 raggiunge il resistore serie da 22 Ω R506.1 con 2,397 mm di rame da 0,20 mm sul fronte, senza cambi di strato. La posa congiunta riduce da 3,817 a 3,445 mm la distanza in linea retta fra il vicino R502.1 e la sua sorgente U1.AA2. Sul file ricaricato il riferimento di massa In1 è continuo ai tre punti trasversali campionati ogni 25 µm o meno. I test locali di uscita dalle piazzole, le connessioni storiche e le riserve meccaniche sono conservati; il DRC non introduce nuove segnalazioni. Il controllo XY del dissipatore conserva libera la sagoma da 13,9 mm. La piastra ipotetica da 16 mm ora intercetta sei componenti invece dei cinque del checkpoint precedente. Il tratto R506.2–U5.20, TXD1, il ritardo MAC/PHY e lo skew del bus completo sono aperti.

## Banco NPU su entrambi i lati

Il checkpoint corrente è `experiments/phy-power-parallel/layout-npu-c434-paired-load.json`, con 406 unioni aperte. C434 (22 µF nominali) è passato sul retro a (79,80; 10,50) mm. Due vie 0,65/0,30 mm a interasse 0,86 mm e piste da 0,80 mm lo collegano a C444.1–L404.2. Il ritorno raggiunge la via di massa esistente a (80,50; 8,60) mm. Il PCB ricaricato conserva i gruppi precedenti, presenta zero nuove segnalazioni DRC e supera il controllo delle riserve di montaggio. La misura di stabilità, il percorso verso il carico e il collegamento Kelvin restano aperti.

## Banco LOGIC su entrambi i lati

Il checkpoint corrente è `experiments/phy-power-parallel/layout-logic-c431-paired-load.json`, con 407 unioni aperte. C431 è stato riposizionato sul retro a (74,50; 9,90) mm. Due vie 0,65/0,30 mm a interasse 0,80 mm e rami di rame da 0,80 mm lo collegano al nodo di uscita già verificato L401.2–C441.1. Il ritorno di C431 raggiunge la via GND esistente a (74,55; 9,00) mm. Sul file ricaricato sono conservati tutti i gruppi di pad precedenti. Il vecchio tratto di massa di C431 è l’unico elemento in rame sostituito. Nessuna nuova segnalazione DRC o interferenza con le riserve meccaniche. La distribuzione al SoC e la verifica di stabilità sono aperte.

## Uscita BUCK4 verso il banco NPU

Il PCB corrente è `experiments/phy-power-parallel/layout-npu-output-cap-c444.json` con 408 unioni aperte. Sul fronte il rame da 0,80 mm fra C444.1 e L404.2 misura 8,24 mm; C444.2 appartiene già alla rete fisica di massa principale. La presa di feedback R424.1 deve ancora raggiungere il punto di misura vicino al carico SoC, come richiesto dallo schema PMIC. Riempimento, DRC e verifica delle connessioni sul file ricaricato conservano tutte le coppie precedenti. Restano da verificare la stabilità dell’anello e la distribuzione DC fino al carico.

## Condensatori di uscita CPU e LOGIC

Il checkpoint adottato è `experiments/phy-power-parallel/layout-logic-output-cap-c441.json` con 409 unioni aperte. I tre rami da 0,80 mm sono stati inseriti e verificati in sequenza sul PCB ricaricato. Sul retro C1608 raggiunge il nodo locale C1601 con 1,75 mm di rame e C1606 raggiunge C1608 con 6,18 mm. L’unica via verso questo gruppo di sfere CPU è ancora 0,45/0,20 mm; la connessione DC dimensionata da L1001 è aperta. Sul fronte il banco di uscita LOGIC C441 raggiunge il pad di uscita L401.2 con 6,99 mm. Tutte le coppie precedenti sono conservate, nessuna nuova segnalazione DRC. Stabilità dei convertitori e impedenza della rete di alimentazione richiedono ulteriori verifiche.


## Collegamento fra i banchi di bypass a 3,3 V

Il PCB adottato è indicato da `experiments/phy-power-parallel/layout-io-bank-copper-contact.json`. Il ramo sul retro fra i gruppi C1627.1 e C1639.1 misura 7,42 mm ed è largo 0,50 mm. Dopo riempimento e ricaricamento KiCad verifica 412 unioni ancora aperte, tutte le coppie precedenti conservate e nessuna nuova segnalazione DRC. La misura riguarda la continuità dei due gruppi. L’impedenza dell’alimentazione e la corrente disponibile ai carichi restano da verificare.


U1.AF24 e U2.D9, Y5 e Y8 raggiungono la massa principale usando quattro raccordi ai via esistenti. Restano 414 unioni aperte. [Checkpoint precedente](experiments/phy-power-parallel/layout-reused-ground-barrels.json) · [Percorsi ricaricati e DRC per raccordo](experiments/phy-power-parallel/bga-reused-ground-barrels.json)

U1.B14 raggiunge ora il rame di massa esistente sullo stesso lato. Restano 413 unioni aperte. [Checkpoint adottato](experiments/phy-power-parallel/layout-ground-copper-contact.json)

## Bypass locale NPU

C1621 da 100 nF raggiunge le cinque sfere VDD_NPU di U1 tramite un via ordinario. Il condensatore era già collegato al piano di massa. Il via GND più vicino dista 1,409 mm; la qualifica d’impedenza del bypass e il collegamento di potenza al regolatore restano aperti. Restano 418 unioni aperte. [Checkpoint precedente](experiments/phy-power-parallel/layout-npu-local-bypass.json) · [Verifica geometrica e dei ritorni](experiments/phy-power-parallel/npu-local-bypass.json)

## Ritorni del processore e della memoria

Dieci nuovi via di massa da 0,45/0,20 mm collegano al piano dodici ulteriori pin del processore e della memoria. Il rame dei via mantiene almeno 0,10 mm dalle piazzole e i fori almeno 0,252 mm dal rame delle altre reti nei controlli geometrici eseguiti. Il DRC sul PCB ricaricato e le coppie precedenti sono verificati. Restano 428 unioni aperte, rispetto a 439 prima dei due passaggi. [Checkpoint intermedio](experiments/phy-power-parallel/layout-bga-ground-remaining.json) · [Primi quattro via](experiments/phy-power-parallel/ground-bga-physical-drops.json) · [Altri sei via](experiments/phy-power-parallel/ground-bga-physical-remaining.json)

La ricerca successiva applica il margine di saldatura e la presenza dei due piani prima di selezionare i siti. Altri nove ritorni arrivano alla massa principale. Il PCB ricaricato conserva 121 segnalazioni storiche e 419 unioni aperte. [Checkpoint precedente](experiments/phy-power-parallel/layout-bga-ground-qualified.json) · [Verifiche individuali](experiments/phy-power-parallel/ground-bga-physical-qualified.json)

## Strobe eMMC

Il pin U8001.H5 raggiunge il pulldown R8005 con 1,14 mm di rame. Il secondo pin del resistore raggiunge la massa principale. Il PWM del display conserva la continuità e il tratto LPDDR4_A1_A riposizionato resta sopra il piano a tutti i 326 punti campionati. Il via di ritorno più vicino dista 1,001 mm. L’apertura del piano sotto la linea strobe si estende fino a 0,415 mm dal centro del via. Il pin host U1.L26 resta da collegare e la temporizzazione completa è da verificare. Restano 439 unioni aperte. [Checkpoint precedente](experiments/phy-power-parallel/layout-emmc-strobe-pulldown.json) · [Verifica dei ritorni](experiments/phy-power-parallel/emmc-strobe-ca-reference.json)

## Punto di test del recupero

R1504 e TP10 sono ora sul retro vicino a U1.D26. Il punto di test raggiunge il pin 1 del resistore e il pin 2 raggiunge C1636.1 sulla rete analogica da 1,8 V. Restano aperti il collegamento al pin ADC del processore e la distribuzione del rail fino a C1636. La riposizione conserva le connessioni precedenti e le riserve meccaniche verificate. Restano 440 unioni aperte. [Checkpoint precedente](experiments/phy-power-parallel/layout-recovery-adc-relocated.json)

## Ritorni GND sotto U1

Quattro piste F.Cu da 0,25 mm, ciascuna lunga 0,919 mm, portano U1.1B9, U1.1L2 e U1.1R12 alla massa principale e uniscono i due gruppi di massa U1.1F15 e U1.1G13. Quest’ultimo gruppo di dieci sfere resta separato dal piano di massa. Sul PCB ricaricato restano 444 unioni aperte e 121 segnalazioni storiche. [Checkpoint iniziale](experiments/phy-power-parallel/layout-ground-surface-islands.json) · [Verifica CAD](experiments/phy-power-parallel/ground-surface-islands.json)

Il passaggio successivo connette C1609.2 e C1618.2 con 2,054 mm di rame su B.Cu. Restano 443 unioni aperte. [Checkpoint intermedio](experiments/phy-power-parallel/layout-ground-surface-bends.json)

C1609 e C1618 raggiungono ora il piano attraverso il via GND esistente alle coordinate (42,90; 18,65) mm. Il raccordo sul retro è lungo circa 3,40 mm. Il circuito necessita ancora della verifica di impedenza del ritorno in frequenza. Restano 442 unioni. [Checkpoint intermedio](experiments/phy-power-parallel/layout-ground-cap-existing-barrel.json)

I dieci pin di massa dei gruppi U1.1F15 e U1.1G13 raggiungono ora il via esistente a (48,45; 24,60) mm attraverso un raccordo F.Cu lungo 6,19 mm. La continuità è verificata sul PCB ricaricato. Restano da dimensionare i ritorni distribuiti sotto U1 per corrente e induttanza. Restano 441 unioni aperte. [Checkpoint precedente](experiments/phy-power-parallel/layout-soc-ground-existing-barrel.json)

## Bypass locale del processore

Sul [checkpoint CPU](experiments/phy-power-parallel/layout-cpu-local-hf-bypass.json), C1601 da 100 nF è montato sotto U1. Un via interstiziale da 0,45/0,20 mm collega il condensatore ai sei pin VDD_CPU e due via di massa esistenti chiudono il ritorno. Le 698 coppie precedenti sono conservate. Le unioni aperte scendono da 449 a 448. Rimane da collegare il gruppo al convertitore dimensionando il percorso per la corrente del processore. La verifica riguarda geometria e continuità CAD. [Controlli sul PCB ricaricato](experiments/phy-power-parallel/cpu-bypass-referenced-preservation.json)

## Uscita BGA con foro esterno alla piazzola

Il [checkpoint precedente](experiments/phy-power-parallel/layout-bga-referenced-barrel.json) porta il via di DQ10_B fuori dalla piazzola U1.B27, mantenendo il diametro di rame di 0,45 mm e il foro da 0,20 mm. Il nuovo via di massa collega i piani interni e riduce la distanza del ritorno da 1,304 a 0,658 mm. Il DRC conserva 121 segnalazioni storiche; il PCB ricaricato conserva 698 coppie già collegate e 449 unioni aperte. [Controlli di conservazione](experiments/phy-power-parallel/bga-referenced-barrel-preservation.json)

Il nuovo tratto da 0,350 mm passa sopra l'apertura del piano attorno al via. Serve il modello dell'intera transizione per verificarne la risposta ad alta frequenza. Dei 113 via di fuga esaminati, 32 fori nominali continuano a intersecare la piazzola di origine. Altre quattro correzioni restano in prova per la distanza del ritorno di massa. [Geometria ricaricata](experiments/phy-power-parallel/ddr-referenced-escape-land-proximity.json)

La variante [DQ9_B da U1.C27](experiments/phy-power-parallel/bga-c27-referenced-barrel.json) usa il ritorno di B27 a 0,782 mm e supera i controlli di continuità e distanza. Il tratto aggiunge 2,769 mm di rame e sposta l'uscita più lontano dalla RAM. La stima planare 2116A del rame presente su DQ9_B cresce di 16,72 ps, mentre DQS1P_B e DQS1N_B sono ancora aperti. Il percorso minimo geometrico passa da 16,97 a 21,09 mm, contro 15,79 e 16,00 mm per le due polarità DQS. La differenza fra minimi geometrici non misura lo skew finale. Il coupon resta separato fino al routing del byte. [Analisi geometrica del byte](experiments/phy-power-parallel/bga-c27-byte-budget.json)

## Primo collegamento del bus comandi LPDDR4

Il [checkpoint CA1, canale A](experiments/phy-power-parallel/layout-command-ca1.json) collega U1.A10 a U2.J2. Il tratto su In3 misura 17,86 mm e conserva 0,20 mm di larghezza. Due nuovi via di massa distano 0,671 e 0,707 mm dai via del segnale. Il controllo geometrico sullo strato adiacente esclude tratti paralleli entro 0,20 mm con angolo inferiore a 15° nel percorso campionato. Il [confronto dei ritorni](experiments/phy-power-parallel/ddr-ca1-plane-impact.json) ha esaminato 32 segmenti preesistenti senza rilevare peggioramenti nell’area proiettata. Restano da qualificare impedenza, ritardi rispetto al clock e margini di setup/hold dell’intero gruppo su entrambi i canali.

Il PCB ricaricato verifica **698 coppie**, con 203 reti aperte, 449 unioni minime e 121 segnalazioni di via ancora senza prosecuzione. Il percorso alternativo CA5 resta sperimentale.

### Studio dei clock LPDDR4

Su una copia del PCB, il [clock B](experiments/phy-power-parallel/ddr-clock-b-recovered.json) collega entrambe le polarità fra processore e RAM e conserva 700 coppie di pad verificate. Il percorso richiede di ricollocare 19 uscite BGA e presenta una differenza di lunghezza P/N di 1,906 mm. Il clock A e i riferimenti temporali dei due bus comando restano aperti. Questi risultati appartengono al coupon sperimentale.

Una [seconda disposizione della coppia B](experiments/phy-power-parallel/ddr-clock-b-preserved-recovered.json) conserva altri tre via originali. Rimangono 16 uscite da ripristinare e 9 nuove segnalazioni di estremità libere rispetto al PCB adottato. Le [lunghezze sul PCB ricaricato](experiments/phy-power-parallel/ddr-clock-b-preserved-budget.json) sono 18,511 mm per P e 16,627 mm per N. La differenza di 1,884 mm richiede una revisione dei tratti terminali e del percorso accoppiato. Nel [campionamento geometrico](experiments/phy-power-parallel/ddr-clock-b-preserved-coupling.json), su In3 oltre 1,42 mm del conduttore P e 1,19 mm del conduttore N hanno un distacco fra i bordi superiore a 0,50 mm. Il modello planare a linee singole non quantifica la conversione di modo in questi tratti.

Sul precedente checkpoint CA1, [33 dei 113 fori di fuga esaminati](experiments/phy-power-parallel/ddr-escape-land-proximity.json) intersecano in pianta il rame della rispettiva sfera. Per queste posizioni servono il confronto con le tolleranze di foratura e registrazione, il disegno della maschera e la conferma del processo di riempimento e metallizzazione oppure una fuga esterna alla piazzola. La continuità CAD da sola non verifica la saldabilità.

## Alimentazione VCCQ e primo tratto DAT0 della eMMC

Il [checkpoint eMMC](experiments/phy-power-parallel/layout-emmc-data-power.json) verifica L405.2–R8006.1, R8006.2–C8002.1 e il pull-up DAT0 da 10 kΩ. La sfera A3 della memoria raggiunge R8001.2 con 18,90 mm di rame e due cambi strato. I via di ritorno più vicini distano 0,90 e 0,91 mm. La connessione a U1.J25, le restanti alimentazioni, la temporizzazione del bus e l’avvio fisico restano da verificare. Il PCB ricaricato conserva 697 coppie con 450 unioni residue e 123 segnalazioni storiche.

## Alimentazione delle sfere N12 e K12

Il [checkpoint N12](experiments/phy-power-parallel/layout-memory-n12.json) verifica L403.2–U2.N12 con una derivazione posteriore da 0,60 mm lunga 8,60 mm e due via lato memoria. La [derivazione verso K12](experiments/phy-power-parallel/layout-memory-n12-neighbors.json) aggiunge 1,47 mm di rame frontale da 0,50 mm. Il PCB ricaricato verifica 694 coppie con 453 unioni residue. Rimane da qualificare il disaccoppiamento locale della sfera.

## Calibrazione ZQ della memoria

Il [PCB ricaricato](experiments/phy-power-parallel/layout-memory-zq-supply.json) unisce il lato alimentazione di R201 alla sfera U2.A4 e all’uscita L403.2 attraverso una derivazione da 0,60 mm lunga 12,70 mm. Il lato opposto del resistore da 240 Ω conserva il collegamento a U2.A5. Risultano verificate 692 coppie con 455 unioni residue e 123 segnalazioni preesistenti. Il comportamento della calibrazione ZQ richiede il sistema fisico e la verifica del rail in esercizio.

## Sezioni dei tronchi di alimentazione della memoria

Il [PCB verificato](experiments/phy-power-parallel/layout-memory-trunk-widths.json) allarga 14 tratti originari fino a 1,40 mm dove rame, fori e segnali adiacenti lo permettono. Nel [modello resistivo](experiments/phy-power-parallel/memory-trunk-widths.json) con rame esterno da 35 µm e interno da 18 µm a 20 °C, il tronco da 1,1 V passa da 66,35 a 43,82 mΩ e quello da 1,8 V da 43,42 a 32,15 mΩ. Entrambi i [piani di riferimento](experiments/phy-power-parallel/memory-trunk-widths-projection.json) conservano la stessa area e sagoma. L’audit conta 690 coppie, 457 unioni aperte e 123 avvisi DRC preesistenti. La resistenza delle vie e la risposta dinamica del circuito richiedono ancora verifica.

## Distribuzione da L403 alla memoria

Il [PCB adottato](experiments/phy-power-parallel/layout-lpddr-vddq-source.json) collega L403.2 a U2.AB4 e al banco di 33 condensatori. Il tragitto misura 46,95 mm su quattro strati con rame largo 0,60 mm. Il ripristino di J3.32–U1.AG19 elimina il moncone del precedente percorso MOSI. La verifica cumulativa conta 690 coppie e 457 unioni aperte; restano 123 avvisi DRC preesistenti. Sono ancora aperti il nodo di commutazione U4.25–L403.1, il feedback del BUCK3 e altre sfere di memoria. La [stima resistiva](experiments/phy-power-parallel/memory-trunk-dc-estimate.json) separa il solo rame del percorso dalle impedenze di via, induttore e regolatore.

## Distribuzione da L405 alla memoria

Nel [PCB adottato](experiments/phy-power-parallel/layout-lpddr-vdd1-source.json) L405.2 alimenta il banco di U2.F1 attraverso 28,18 mm di piste da 0,60 mm, con due vie a ogni estremità della distribuzione interna. La rete di commutazione U4.53–L405.1 e il ritorno di misura U4.59 sono connessi. Il [controllo delle proiezioni](experiments/phy-power-parallel/vdd1-source-barrel-projections.json) confronta le due piste vicine ai quattro fori introdotti o allargati. Il totale è di 687 coppie CAD verificate e 458 unioni residue. Restano la distribuzione alle altre sfere e le verifiche di caduta di tensione, transitori e temperatura.

## Rail VDD1 della LPDDR4

Sul [PCB ricaricato](experiments/phy-power-parallel/layout-lpddr-vdd1-bank.json) C2302, C2304, C2306 e C2307 raggiungono la sfera U2.F1 attraverso il banco C2305/C2308. Il nuovo tratto sul retro misura 7.50 mm ed è largo 0,50 mm. L405, sorgente del rail, resta separato. La verifica cumulativa conta 685 coppie, 459 unioni aperte e 123 avvisi preesistenti.

## Risveglio host dal modulo Wi-Fi

Sul [PCB verificato con ritorni di massa](experiments/phy-power-parallel/layout-radio-returns.json) U25.13 raggiunge U1.V26. Il passaggio dal retro usa una via da 0,45/0,20 mm; il reset del PHY adiacente conserva i due punti di connessione originali. Restano 460 unioni minime aperte tra i pad presenti su 204 reti. Due vie di massa collegano i piani a 0,71 e 0,82 mm dalle rispettive transizioni del segnale, rispetto ai precedenti 1,57 e 5,55 mm. Il terzo punto esaminato resta a 3,01 mm. Il percorso completo di risveglio misura 73,42 mm e comprende otto vie; la risposta elettrica resta da qualificare. Le 681 coppie fisiche sono state ricontrollate e il DRC segnala 123 vie pendenti preesistenti. La [verifica dello schema](experiments/phy-power-parallel/routed-schematic-review.md) identifica separatamente i dieci terminali funzionali del display ancora assenti dal PCB.

## Banco GPU

Il [PCB ricaricato](experiments/phy-power-parallel/layout-gpu-cap-bank.json) collega C1619 e C1620 con 7,38 mm di rame largo 0,60 mm sul retro. Entrambi i condensatori raggiungono la massa di U4.69. Restano da collegare L402 e il carico U1. Il controllo cumulativo copre 680 coppie su 205 reti, con 461 unioni aperte e 123 segnalazioni DRC preesistenti.

## Checkpoint corrente del banco di bypass LPDDR4

Il [PCB verificato](experiments/phy-power-parallel/layout-memory-cap-return.json) unisce tutti i 33 condensatori da C1646 a C1678, TP7 e la sfera U2.AB4 su +1V1_LPDDR4. L’ultimo tratto è lungo 2,41 mm e largo 0,50 mm. C1648 e la sua via di massa sono stati spostati insieme di 0,106 mm. Il [controllo del ritorno](experiments/phy-power-parallel/memory-bank-cap-return-projection.json) conferma la copertura sotto le tre piste vicine e la distanza dalla massa delle tre vie di segnale circostanti. Il totale è di 677 coppie e 462 unioni aperte su 205 reti, con 123 avvisi preesistenti. La distribuzione dall’induttore L403 e verso le altre sfere resta da completare.

## Collegamenti del banco a 1,1 V

Sul [PCB con derivazione posteriore](experiments/phy-power-parallel/layout-memory-bank-rear-taps.json), C1669.1 e C1677.1 raggiungono U2.AB4 e C1666.1 mediante 2,32 mm di rame largo 0,50 mm sul retro. La verifica cumulativa conta 676 coppie, 463 unioni aperte e 123 avvisi DRC preesistenti. Il gruppo di C1663, C1668 e C1676 è ancora separato, come l’uscita dell’induttore L403.

## Alimentazione LPDDR4

Sul [PCB adottato](experiments/phy-power-parallel/layout-memory-ab4-bank.json), U2.AB4 e il suo condensatore C1674 sono connessi al banco di C1666 su In3. Le diramazioni da 0,50 mm utilizzano due passaggi paralleli al lato del banco. Il controllo cumulativo conta 675 coppie, 464 unioni aperte su 205 reti e 123 avvisi di via pendente. La [proiezione sullo strato adiacente](experiments/phy-power-parallel/memory-ab4-bank-broadside.json) individua due attraversamenti di +3V3_IO e nessuna pista dati entro il margine analizzato di 0,35 mm. La [normalizzazione geometrica](experiments/phy-power-parallel/memory-ab4-normalized.json) rimuove dieci segmenti completamente ricoperti da rame collineare della stessa rete. L’uscita dell’induttore L403 e le altre sfere di alimentazione della memoria richiedono ancora collegamenti.

## Bypass della memoria

Il [PCB ricaricato](experiments/phy-power-parallel/layout-memory-ab4-bypass.json) collega la sfera U2.AB4 al condensatore da 100 nF C1674, riposizionato sul retro. Due vie da 0,45/0,20 mm trasferiscono il rail da 1,1 V e due il ritorno. Il ramo positivo più lungo misura 4,87 mm ed è largo 0,50 mm. La copertura di massa sotto le piste LPDDR esistenti coincide nel [controllo precedente](experiments/phy-power-parallel/lpddr-return-before-ab4.json) e in quello [successivo allo spostamento](experiments/phy-power-parallel/lpddr-return-after-ab4.json), campionati ogni 0,025 mm. L’audit conta 674 coppie, 465 unioni aperte e 123 avvisi preesistenti. L’efficacia del bypass alle frequenze della memoria resta da qualificare.

## Ritorni della memoria

Il [PCB ricaricato](experiments/phy-power-parallel/layout-ground-land-offsets.json) aggiunge quattro collegamenti di massa fra sfere vicine della LPDDR4 e porta altre 17 sfere al gruppo di massa di U4.69 mediante tratti da 0,30 mm di larghezza e da 0,73 a 1,84 mm di lunghezza. Il totale è di 672 coppie verificate, 466 unioni aperte su 205 reti e 123 avvisi di via pendente. Questi dati misurano la continuità CAD.

## Ritorni del SoC

Sul [PCB verificato](experiments/phy-power-parallel/layout-soc-ground-neighbors.json) 30 ulteriori sfere di U1 raggiungono la massa di U4.69. Sono state controllate sia le nuove coppie di pad sia l’appartenenza di ciascuna sfera al gruppo di massa centrale. La verifica cumulativa conta 651 coppie distinte e 487 unioni aperte su 205 reti. Il DRC mantiene i 123 avvisi di via pendente. Il confronto copre la continuità CAD. L’impedenza dei ritorni ad alta frequenza richiede una verifica separata.

## Alimentazioni del SoC

Il [PCB ricaricato](experiments/phy-power-parallel/layout-soc-core-neighbors.json) collega U1.1E8–U1.1E9 sul rail LPDDR4 da 1,1 V e U1.1G10–U1.1H10 su VDD_LOGIC. Entrambe le piste misurano 0,45 mm e sono larghe 0,50 mm. Il controllo cumulativo conta 621 coppie distinte, 517 unioni aperte su 205 reti e 123 avvisi di via pendente. La distribuzione a monte dei due banchi resta incompleta.

## Controllo USB e alimentazione eMMC

Il [PCB con controllo di orientamento USB-C](experiments/phy-power-parallel/layout-usb-direction-complete.json) collega U6.11 al pull-up R602.2. La via attraversa lo spazio liberato da C1665. Il controllo KiCad conta 619 coppie distinte, 519 unioni minime aperte su 205 reti e 123 avvisi via_dangling preesistenti. La commutazione con cavo reversibile richiede una prova su prototipo.


Il [PCB verificato con C1665 riposizionato](experiments/phy-power-parallel/layout-memory-bank-c1665.json) collega il condensatore da 100 nF al banco da 1,1 V della LPDDR4 e alla massa. Il ramo positivo misura 1,11 mm. La verifica sul PCB ricaricato conta 618 coppie distinte, 520 unioni minime aperte e 123 avvisi via_dangling preesistenti.


Sul [PCB adottato](experiments/phy-power-parallel/layout-emmc-perimeter-supply.json) le sfere M4 e N4 di U8001 sono unite da 0,30 mm di rame largo 0,35 mm sulla rete I/O a 1,8 V. Le sfere J10 e K9 sono collegate da 2,24 mm di rame largo 0,30 mm sulla rete a 3,3 V. Entrambi i percorsi sono sul lato del componente. Dopo il ricaricamento risultano 616 coppie verificate e 521 unioni aperte su 206 reti, con 123 avvisi di via pendente preesistenti. L’alimentazione e l’avvio della eMMC richiedono ancora il completamento della distribuzione.

## Antenna esterna sul layout USB corrente

Sul [coupon U.FL aggiornato](experiments/phy-power-parallel/rf-external-usb-direction.json) le modifiche al layout USB ed eMMC conservano i gruppi di pad preesistenti, i fissaggi e il risultato del DRC. Le [sette verifiche RF e di massa](experiments/phy-power-parallel/rf-external-plane-projection-usb-direction.json) passano per entrambe le geometrie in esame. Per lo stack 3313 le piste larghe 0,154 mm violano otto volte la regola di larghezza. Sul 7628 le aperture di tre pin passanti Ethernet interrompono il margine laterale di massa di 0,20 mm sotto le piste. La [mappa degli ostacoli](experiments/phy-power-parallel/rf-external-reference-obstructions.json) identifica i pin per UUID. La [ricerca delle deviazioni](experiments/phy-power-parallel/rf-external-plane-detours.json) a passi di 0,10 mm e con i pad fissi non ha trovato un percorso nella finestra locale. Il coupon resta separato dal PCB adottato.

## Coupon del PMIC ruotato

Sul [coupon verificato](experiments/phy-power-parallel/runs/rotated-buck-return-pair-C422-C432/boundary-contracts.json) sono stati recuperati dieci ritorni di condensatori. Il primo passaggio ha chiuso C482, il secondo sette ulteriori condensatori e i due successivi C412 e C483. Sono state ripristinate le dieci connessioni tra le masse perimetrali del PMIC e il pad esposto. Entrambe le linee di gestione I²C raggiungono i rispettivi resistori. Per SCL è stata riutilizzata una via già collegata al pin U4.1. Le piste da 0,50 mm collegano anche U4.45 e U4.33 al gruppo di alimentazione di C1304.1. Sul retro, percorsi da 0,50 mm uniscono i positivi di C421/C422 e C423/C482/C483. Il banco C423/C482/C483 raggiunge C1304.1 con due vie distanziate di 0,608 mm e piste da 0,50 mm. Il banco C421/C422 attende la connessione alla sorgente. Il ritorno locale tra C422 e C432 misura 2,35 mm con una pista da 0,60 mm e richiede ancora il collegamento al piano di massa. Restano 25 ricongiungimenti per recuperare i gruppi della baseline del coupon. L’alimentazione dei cinque convertitori e la risposta sotto carico sono ancora da completare e qualificare. Una prova con un piano locale sul retro unisce quattro condensatori in KiCad. La verifica del corridoio di ritorno largo 0,60 mm (0,30 mm per C470) trova una sola via raggiungibile da C432 e nessuna dagli altri tre entro 2,4 mm. La [verifica dei percorsi](experiments/phy-power-parallel/rotated-buck-plane-paths.json) e la [mappa dei siti di foratura](experiments/phy-power-parallel/rotated-buck-plane-barrel-screen.json) tengono il piano su un coupon separato.

## Checkpoint dei filtri analogici USB

Sul [PCB ricaricato](experiments/phy-power-parallel/layout-usb-analog-1v8.json) il filtro a 1,8 V collega C1635.1 a R1602.1 e R1602.2 a C1682.1. C1682.2 raggiunge la massa di U4.69. La verifica cumulativa conta 614 coppie, 523 unioni aperte su 206 reti e 123 avvisi preesistenti di via pendente. Il PMIC e le sfere analogiche USB del SoC richiedono ancora il completamento dei percorsi di alimentazione.

## Checkpoint del filtro analogico USB a 0,9 V

Il [PCB adottato](experiments/phy-power-parallel/layout-usb-analog-0v9.json) collega R1601.1 a C1642.1 e R1601.2 al banco C1679.1–C1680.1. Il trasferimento conserva il rame precedentemente adottato e sposta R1601 fuori dalla zona proposta per l’antenna interna. Il controllo cumulativo sul file ricaricato verifica 611 coppie di pad e conta 525 unioni aperte su 206 reti. Il DRC riporta i 123 avvisi di via pendente già presenti. L’alimentazione dal regolatore e il collegamento alla sfera USB del SoC sono ancora aperti.

## Checkpoint del controllo USB

Il [PCB adottato](experiments/phy-power-parallel/layout-usb-enable-trunk.json) collega il consenso del mux da U16.4 a U6.12 con un tronco da 6,70 mm. Il tratto adiacente AON_READY è stato reinstradato a larghezza invariata di 0,20 mm. La verifica del PCB ricaricato conta 608 coppie distinte verificate, 527 unioni ancora da chiudere su 206 reti e 123 avvisi di via pendente preesistenti. La commutazione e il funzionamento SuperSpeed richiedono il completamento dei collegamenti USB e la prova su prototipo.

## Checkpoint della selezione del display

Il [PCB adottato](experiments/phy-power-parallel/layout-lcd-select-trunk.json) collega U1.M3 a U21.6 e R1815.1 con 14,71 mm di nuovo tronco LCD_CS_N. Il ritorno dedicato di U1.1F1 raggiunge la propria via con un tratto da 0,30 mm largo e 0,478 mm lungo. La [verifica del riferimento LPDDR4](experiments/phy-power-parallel/lpddr-return-after-display.json) conserva la copertura di massa già campionata. L’audit conta 607 coppie distinte, 528 unioni su 207 reti e 123 avvisi preesistenti. Restano aperti il reset e i dati del display lato SoC.

## Checkpoint del clock del display

Il [PCB verificato](experiments/phy-power-parallel/layout-lcd-clock-trunk.json) collega U1.N3 a U21.3 e R1812.1 sulla linea LCD_SCLK. Una traslazione di R8001 di 0,10 mm, con orientamento invariato, libera l’uscita del SoC preservando la connettività eMMC. Il nuovo tronco misura 16,43 mm. Restano aperti MOSI, CS e reset lato CPU. L’audit conta 605 coppie distinte, 529 unioni minime su 208 reti e 123 avvisi preesistenti di via pendente.

## Checkpoint del consenso di accensione CPU

Il [PCB adottato](experiments/phy-power-parallel/layout-cpu-enable-bias.json) chiude il pull-up da 51 kΩ del regolatore CPU. R1002.1 raggiunge la distribuzione +3V3_PMU e R1002.2 raggiunge U10.A2. La [modifica al gomito di WIFI_VBAT](experiments/phy-power-parallel/cpu-enable-vbat-elbow.json) conserva la larghezza di 1,00 mm su In3 e abbrevia quel tratto di 0,143 mm. Dopo ricarica e DRC risultano 603 coppie distinte verificate, 530 unioni minime aperte su 209 reti e 123 avvisi preesistenti. Il collegamento della sorgente U4.31 alla distribuzione +3V3_PMU rimane aperto.

## Checkpoint del chip-select SPI di espansione

Il [PCB adottato](experiments/phy-power-parallel/layout-exp-spi0-pullup.json) collega J3.34, U1.AG17 e R2103.1 sulla prima linea di selezione SPI. R2103.2 torna al gruppo di alimentazione +3V3_PMU. Il [controllo del ritorno all’alimentazione](experiments/phy-power-parallel/exp-spi0-restore-feed.json) e l’audit cumulativo verificano 602 coppie distinte, con 531 unioni aperte su 209 reti e 123 avvisi preesistenti. La sorgente della tensione +3V3_PMU e la seconda linea di selezione richiedono ancora cablaggio.

## Checkpoint del bus I²C di espansione

Il [PCB ricaricato](experiments/phy-power-parallel/layout-exp-sda-complete.json) collega entrambe le linee I²C del SoC a J3 e ai resistori da 4,7 kΩ. Su SDA sono stati verificati U1.AE15, J3.23 e R2101.1. R2101.2 raggiunge U4.55. Il ritorno di massa sul retro del SoC e GPIO1 vicino al connettore conservano i collegamenti verificati. L’audit conta 599 coppie distinte, 532 unioni minime aperte, 210 reti aperte e 123 avvisi preesistenti.

La [stima dei tempi di salita](experiments/phy-power-parallel/exp-i2c-rise-estimate.json) considera 95,54 mm di rame per SDA e 56,01 mm per SCL. I due stack esaminati danno circa 9,8 pF e 5,7–5,8 pF per le sole piste. Con i pull-up nominali rimangono circa 65 pF di margine su SDA per contenere la salita entro 300 ns a 400 kHz. Questo margine deve coprire pad, vie, pin e accessorio. La misura sul prototipo e sul modulo di espansione completerà la verifica.

## Checkpoint delle alimentazioni dei pull-up

Il [PCB verificato](experiments/phy-power-parallel/layout-wifi-io-pullup-bank.json) collega alla tensione I/O i due resistori di pull-up I²C dell’espansione e quattro dei cinque resistori di pull-up SDIO. J3.24 raggiunge R2102.1 e U4.55 raggiunge R2102.2. Sul modulo Wi-Fi U25.14 raggiunge R2012.1 e R2012.2 raggiunge la tensione I/O. Restano aperti la linea dati I²C dell’espansione, l’alimentazione di R2011 e parte del cablaggio SDIO. L’audit conta 596 coppie di pad distinte dopo la normalizzazione dei versi, 534 unioni minime aperte su 211 reti e 123 avvisi di via pendente.

## Checkpoint del piano di riferimento LPDDR4

Il [PCB adottato](experiments/phy-power-parallel/layout-lpddr-dq0-reference.json) riposiziona due vie delle linee DQ4_B e DQ5_B per riportare rame di massa sotto DQ0_B. Dopo il riempimento e la ricarica, tutti i 72 punti della finestra campionata sul piano hanno massa, rispetto agli otto precedenti. La [verifica geometrica](experiments/phy-power-parallel/lpddr-dq0-reference.json) conserva larghezza e foratura, le 589 coppie già validate e i tre ritorni di clock. Restano 540 unioni minime aperte su 211 reti e 123 avvisi di via pendente. Questa verifica riguarda la geometria locale.

## Checkpoint dei ritorni di clock LPDDR4

Il [PCB adottato e ricaricato](experiments/phy-power-parallel/layout-lpddr-clock-return.json) aggiunge tre vie di massa passanti da 0,45/0,20 mm fra i due piani di riferimento. Sul lato RAM di entrambi i canali, la via di ritorno dista al più 1,01 mm dalle due vie della coppia di clock. Sul lato SoC del canale A la distanza massima è 1,48 mm. I [riscontri geometrici](experiments/phy-power-parallel/lpddr-clock-return-stitches.json) comprendono il rame attorno alle nuove vie su entrambi i piani e la connettività con la massa del PMIC. Il controllo cumulativo conserva 589 coppie e conta 540 unioni aperte su 211 reti e 123 avvisi preesistenti di via pendente. Il clock end-to-end e il timing RAM restano aperti.

Il [confronto simulato dei due stack a sei strati](experiments/phy-power-parallel/usb-ddr-stack-simulation.json) distingue i segnali esterni da quelli sulle due facce interne di segnale. Sul 7628, assumendo Dk 4,4, le coppie esterne larghe 0,30 mm con gap 0,25 mm raggiungono circa 91 Ω; con larghezza 0,24 mm raggiungono circa 100 Ω. Sul 3313 le stesse geometrie esterne danno circa 65 e 74 Ω. Il [modello MDI](experiments/phy-power-parallel/outer-pair-impedance-simulation.json) esplicita geometria del rame, maschera e convergenza numerica. Lo stack definitivo, le tolleranze di fabbricazione, le discontinuità ai package e la misura sul coupon restano da qualificare.

## Checkpoint del filtro di accensione

Il [PCB verificato](experiments/phy-power-parallel/layout-pmic-pwron-filter.json) porta il condensatore C412 da 100 nF sul retro del PMIC. U4.52 raggiunge C412.1 attraverso una via passante. Il ritorno di C412.2 raggiunge la massa comune di U4.69 con una pista da 0,30 mm. Il controllo cumulativo dopo ricarica verifica 589 coppie, 540 unioni minime ancora aperte su 211 reti e 123 vie pendenti. La prova di accensione e le forme d’onda richiedono un prototipo.

Il [coupon del partitore VDC](experiments/phy-power-parallel/runs/vdc-placement-0/restore-status.json) unisce U4.61 ai tre componenti del filtro e chiude entrambi i ritorni del partitore. Rimangono da ripristinare il feedback BUCK5, il positivo del partitore e il ritorno di C481. Il coupon è separato dal PCB corrente.

Sul [coupon di riposizionamento congiunto del PMIC](experiments/phy-power-parallel/runs/pmic-five-stage-secondary-0/boundary-contracts.json) le cinque uscite di commutazione raggiungono i rispettivi induttori e ciascun induttore raggiunge il suo condensatore principale. BUCK5 recupera sette degli otto collegamenti locali del progetto originario, compresi il feedback prelevato su C435 e il secondo condensatore d’uscita C445. Rimane aperta U4.54–C425.1. Le due bancate del connettore di espansione raggiungono il ramo originale da 1 mm su In3. Il coupon conserva 537 delle 589 coppie del PCB corrente. Restano 54 ricongiungimenti minimi per recuperare i gruppi originari e 586 per chiudere tutte le reti del coupon. Sono verifiche di continuità e geometria in KiCad. Il comportamento dei regolatori sotto carico richiede misure.

## Checkpoint del bus Ethernet RGMII

Il [PCB ricaricato](experiments/phy-power-parallel/layout-soc-tx-series.json) collega U1.AA1 a R501.1 con 1,190 mm di rame da 0,20 mm senza vie. È chiuso il tratto sorgente di TXD0. Restano da realizzare il tratto lato PHY e la verifica dei tempi del bus. Il controllo cumulativo conta 587 coppie, 541 unioni minime aperte su 212 reti e 123 vie pendenti.

Il [checkpoint del ramo ricevente](experiments/phy-power-parallel/layout-phy-source-series.json) collega l’uscita RXD1 del PHY, U5.24, al resistore serie R508.2 con una pista da 0,20 mm lunga 2,229 mm, senza vie. Nel modello CAD il percorso presenta rame GND su In1 lungo la derivazione. Restano da collegare il resistore di strap e il percorso R508–SoC e da verificare impedenza, tempi del bus e funzionamento fisico. Il DRC differenziale sul PCB ricaricato conserva le protezioni preesistenti.

## Checkpoint del connettore Ethernet

Il [PCB verificato](experiments/phy-power-parallel/layout-hanrun-hole-stagger.json) corregge di 0,110 mm i centri dei cinque fori pari di J2, da P2 a P10. Il [disegno HanRun HR911130A, pagina 2](../reference/HR911130A.pdf) quota P6 a 0,64 mm dall’asse e 2,54 mm fra pin consecutivi della stessa fila. Una pista di ritorno GND da 0,40 mm conserva i suoi terminali e passa 0,10 mm più lontano da P2. Il [confronto dimensionale e DRC](experiments/phy-power-parallel/hanrun-hole-stagger.json) conserva tutte le connessioni già verificate. Il montaggio richiede riscontro sul campione fisico.

P10 è il ritorno del condensatore interno da 1 nF / 2 kV della terminazione lato cavo, come indicato a pagina 1 del disegno HanRun. Il [controllo della regione chassis](experiments/phy-power-parallel/ethernet-chassis-clearance.json) individua entrambi i piani GND sotto i due possibili collegamenti diretti. Il PCB mantiene aperta la definizione della regione chassis e la qualifica EMC.

## Checkpoint del rame sovrapposto

Il [PCB ricaricato e verificato](experiments/phy-power-parallel/layout-coincident-cleanup.json) conserva 585 coppie, con 543 unioni minime aperte su 213 reti e 123 vie pendenti. Sono state eliminate 149 copie perfettamente sovrapposte di segmenti rettilinei. Per ogni UUID rimosso è registrato il segmento equivalente ancora presente. Restano 6.593 oggetti fra piste e vie. Il DRC differenziale e la connettività nativa confermano il risultato.

Il [coupon USB](experiments/phy-power-parallel/usb-selective-padfield.json) trova una geometria delle due derivazioni reversibili con due vie per polarità, lunga rispettivamente 3,411 e 3,576 mm. Per ripristinare CC1, CC2 e +3V3_AON dopo questo spostamento serve un'altra disposizione dei lanci. Il [controllo del primo ripristino](experiments/phy-power-parallel/usb-restored-pair-0.json) individua la strozzatura attorno a J1.B5. La coppia è attualmente esclusa dal PCB verificato.

## Checkpoint dei collegamenti locali del SoC

Il [PCB verificato dopo il salvataggio](experiments/phy-power-parallel/layout-cpu-load-sense.json) comprende 33 collegamenti locali fra pad GND di U1 su rame da 0,50 mm. Due ulteriori tratti da 0,50 mm collegano pad di VDD_CPU e VDD_LOGIC. Otto rami da 0,50 mm uniscono altri gruppi alla massa comune. Altri sette ritorni da 0,50 mm raggiungono il rame di massa esistente, inclusi U2.G12 e U2.P1. Un via passante da 0,45/0,20 mm porta al piano il gruppo di quattro pad attorno a U1.1J4 con un tratto da 0,361 mm. Sette rami da 0,50 mm completano collegamenti locali tra condensatori del rail LPDDR4 da 1,1 V. Tre ulteriori rami collegano i condensatori C1679–C1680, C2304–C2302 e C1603–C1604. Sul retro R2012.1 raggiunge U25.14 con un ramo di pull-up da 1,763 mm su WIFI_D2. Restano da collegare il rail del resistore e il segnale verso il SoC. TP6 misura il ramo +3V3_IO di U25, TP7 il gruppo di bypass +1V1_LPDDR4 di C1650. TP8 misura VDD_CPU sul ramo di C1603. I tre pad di misura da 1 mm sono sul retro. Sono verificate 585 coppie. Restano 543 unioni minime su 213 reti e 123 via con estremità aperta. I gruppi locali richiedono ulteriori ritorni al piano di massa.

## Checkpoint delle derivazioni di alimentazione

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
