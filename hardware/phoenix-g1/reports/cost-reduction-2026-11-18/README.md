# Riduzione costi — 18 novembre 2026

Studio di sourcing; nessuna modifica CAD/BOM. USD 1+, esclusi PCB, assemblaggio, IVA, trasporto e componenti non selezionati. Presale/overseas non garantiscono allocazione PCBA.

Base attuale: $92.9121. RAM $25.0845 + eMMC $17.7750 = $42.8595, 46.1% del totale.

|Codice|MPN|USD|Presale|Overseas|
|---|---|---:|---:|---:|
|[C601079](https://jlcpcb.com/partdetail/C601079)|FEMDNN008G-08A39|44.2647|0|0|
|[C2918717](https://jlcpcb.com/partdetail/C2918717)|AP6275S|12.462|408|414|
|[C44425983](https://jlcpcb.com/partdetail/C44425983)|EMMC04G-MT32-02A02|70.8984|4|4|
|[C27682137](https://jlcpcb.com/partdetail/C27682137)|EMMC04G-CT32-01G10|15.8588|0|0|
|[C29342869](https://jlcpcb.com/partdetail/C29342869)|EMMC04G-MT32-01G02|73.2618|0|0|
|[C500273](https://jlcpcb.com/partdetail/C500273)|KLM4G1FETE-B041|21.4813|289|310|
|[C27300677](https://jlcpcb.com/partdetail/C27300677)|D0811PM2FDGUK-U|8.5542|0|0|
|[C2803257](https://jlcpcb.com/partdetail/C2803257)|K4F8E304HB-MGCJ|5.5735|0|0|
|[C2980378](https://jlcpcb.com/partdetail/C2980378)|IMH512M32H2D2ENA|8.4707|0|0|
|[C2920216](https://jlcpcb.com/partdetail/C2920216)|K4F4E3S4HF-GHCJ|4.2616|0|0|
|[C2840158](https://jlcpcb.com/partdetail/C2840158)|RS512M32LM4D2BDS-53BT|13.3431|0|0|

## Risultato

Nessuna sostituzione più economica e disponibile qualificata nel campione. Le cinque RAM economiche ricontrollate sono tutte a quantità zero. Samsung 4 GB costa più della 8 GB attuale; Kingston 4 GB più economica è indisponibile. Il vecchio prezzo indicizzato FORESEE da $7.61 è smentito dal prezzo JLC live $44.2647 con quantità zero.

AP6275S costa $4.1747 in più di AP6256: è un possibile upgrade da qualificare, non un saving. Wi-Fi 5 può superare 433 Mbps: il limite riguarda il modulo attuale 1×1, non lo standard. Preservare USB3 device: RK3562 condivide PHY USB3/PCIe, quindi Wi-Fi PCIe non è una sostituzione diretta. SDIO SDR104 4 bit ha tetto lordo 832 Mbps, non gigabit utile. Fonte: https://rockchip.fr/RK3562%20datasheet%20V2.1.pdf

## Priorità

1. Quotazione sourcing JLC delle memorie economiche: verificare reale approvvigionamento prima di rifare CAD. Non acquistare.
2. Qualificare ballout, tensioni, loader DDR, boot e lifecycle della candidata reperibile.
3. Mantenere display e connettore: incidono poco rispetto alle memorie. Non eliminare protezioni o decoupling per risparmiare.

Questa ricerca è mirata e non esaustiva. Nessun prezzo a stock zero è conteggiato come risparmio ottenuto.
