# Variante di orientamento J3 — studio separato

Il connettore DF40 è ruotato di 180° allo stesso centro (67,5; 2,5 mm),
con numerazione e reti dei pin invariate. Il PCB principale non è stato sostituito.
L'orientamento della futura scheda figlia andrà coerentemente verificato.

`tools/rebuild_rotated_expansion_study.py` ricostruisce alimentazione, massa,
controlli e riferimento logico. La pipeline completa è passata il 14 novembre
2026. Gli UUID dei nuovi segmenti possono cambiare durante la rigenerazione.

`pcb/aux-io-miso-hop-audit.json` documenta sei segnali ausiliari collegati:
UART TX, GPIO2, SDA, clock SPI, MOSI e MISO. UART RX, GPIO3, SCL e i due
chip select restano aperti. MISO attraversa In2.Cu e B.Cu con una via aggiuntiva;
nessuna qualifica temporale o d'impedenza deriva dalla continuità.

Gli audit conservano i 2.460 segmenti/via iniziali e tutte le reti dei pad.
Restano le 139 violazioni preesistenti; il confronto anche per UUID degli
oggetti non rileva nuove violazioni. Tutte le cinque riserve meccaniche sono
presenti, ma non costituiscono fori reali o fissaggi liberati dai componenti.

La variante non è ancora preferibile in modo definitivo: rispetto al checkpoint
principale guadagna segnali ma perde SCL e CS0 già collegati nell'altro layout.
Il numero totale da solo non basta per promuoverla. USB, correnti, termica,
processo delle uscite BGA e fabbricabilità restano da qualificare.

Non pronta alla produzione. Nessuna prova fisica.

## Confronto con ordine di instradamento diverso

`pcb/aux-io-constrained-first-audit.json` verifica sette segnali: UART TX,
GPIO2/3, SDA/SCL, MISO e CS1. La coppia I2C è continua, ma SPI resta incompleta
(clock e MOSI aperti) e UART RX/CS0 restano aperti. Anche questa variante supera
il confronto individuale delle violazioni DRC senza essere un superset del
checkpoint principale. Non è stata promossa.
