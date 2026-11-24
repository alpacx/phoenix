# Display attachment review — 2026-11-18

No CAD or BOM is changed. The13 missing DS1 pads cannot honestly be closed by selecting a generic FPC connector.

New checks exclude Hirose FH12-8S-0.5SH(55) and XUNPU FPC-05F-8PH20 as direct mates for the previously investigated C08 panel: their required exposed-contact and stiffener lengths exceed the panel dimensions. HS096T01H13 retains the same problematic13-contact flex architecture. XUNPUH15 is on hold because its publicPDF is invalid; XYECONN is on hold because a mating drawing was not retrieved. Previous exclusions were read, not retried.

A complete Waveshare0.96inchLCDModule(SKU15868) avoids custom bonding by purchasing the already assembled display board. Official documentation gives32.5×26mm, ST7735S160×80,3.3V/5V supply with matching logic, andPH2.0 8-pin interface. The manufacturer schematic is archived. This preserves the color non-touch display and separate command, but requires mechanical and power-interface changes; direct listedprice isUSD6.99 and JLC availability for this exactmodule was not established. It is a documented fallback, not a selectedBOMpart.

The production path remains blocked on documented mating/bonding for the exact rawpanel or a qualified alternativemodule. Samples and mounting verification remain necessary even after documents match. No party contacted and no order placed.

`review.json` contains exact candidate reasons, source pages, decision limits and hashes. `sources/*.json` contains fresh publicJLC observations, not reservedPCBAstock.

Schematic visual check: J1 and J2 use reversed pin numbering. BL is a logic input through1kΩ to an S8050 base, with10kΩ pull-up toVCC: floatingBL can turn the backlight on. Preserve reset-off via active low control or switched modulepower; do not assume existing rawpanel driver maps directly.

## Impronta di prova per il collegamento diretto

La libreria ufficiale EasyEDA di LCSC associa al codice C2890616 un’impronta con tredici piazzole rettangolari da 0,40 × 2,20 mm, a passo 0,70 mm. Il [coupon KiCad](coupons.pretty/DS1_H13_DirectFlex_Coupon.kicad_mod) conserva numerazione e coordinate, verificate dopo la rilettura. La distanza di 8,40 mm fra i centri dei contatti estremi coincide con il disegno Wisevision. La [verifica](direct-flex-land-review.json) confronta i tredici numeri con la netlist, compresi i tre NC. [Libreria del componente](https://easyeda.com/api/products/C2890616/components?version=6.5.22) · [Disegno del produttore](https://datasheet.lcsc.com/datasheet/pdf/2fcf1691a36c56b1ed6d83dcbd39868e.pdf?productCode=C2890616)

Il campione permette di provare il fissaggio diretto. L’orientamento del flex montato e piegato, l’accesso dell’utensile, il sostegno del vetro e il processo di saldatura restano da qualificare. Il PCB adottato conserva la situazione precedente di DS1.

Sul retro del PCB da 90 × 40 mm la fila di contatti entra a X 23,75 e Y 35,25 mm lasciando 4,75 mm dal centro al bordo sud. Il [coupon inserito nel PCB](rear-mounted-coupon-check.json) conserva la continuità precedente. Le due masse del display raggiungono U4.69 e il pin di alimentazione 10 raggiunge il regolatore U20.5 e i condensatori C1802, C1811 e C1812. Il percorso da 3 V utilizza 5,52 mm di pista da 0,30 mm e una via 0,45/0,20 mm. Dopo il riempimento dei piani e la riapertura del file, questi tre collegamenti portano da 361 a 358 le unioni nella copia con display. Il PCB adottato, privo del footprint DS1, resta a 351. [Masse](rear-coupon-ground-verification.json) · [Alimentazione](rear-coupon-power-native.json)

La scelta del retro richiede che il flex aggiri il bordo della scheda. Le ubicazioni vicine alla presa RJ45 hanno spazio elettrico sul retro ma la presa può impedire il montaggio del pannello sul davanti. La [ricerca sul fronte](coupon-access-before-relocation.json) ha escluso 23 posizioni con ritocchi locali alle vie e vincoli invariati. Raggio di piega, volume dell’utensile per la saldatura e sostegno del vetro richiedono ancora una verifica specifica.

Sul coupon i cinque segnali logici sono instradabili singolarmente. Inserendoli insieme, la [prima variante](rear-coupon-spi-native.json) collega clock, CS e D/C senza nuove violazioni geometriche, con discontinuità del piano di riferimento ancora presenti. Nella [variante a cinque segnali](rear-coupon-negotiated-native.json) i cortocircuiti fra piste e vie la rendono inutilizzabile. Il tentativo di portare ciascuna uscita di U21 direttamente a una via ordinaria entro 2,2 mm non ha prodotto un sito libero per nessuna delle cinque uscite. [Accesso alle uscite del buffer](u21-output-bank-access.json)

Prima di accettare un riposizionamento del buffer vanno ricongiunte anche le 16 coppie già validate che lo interessano. La scelta con minor impatto oggi è mantenere separato il coupon di alimentazione a tre contatti dal banco segnali sperimentale. Alimentazione, clock, dati e backlight richiedono ancora una prova su campione.
