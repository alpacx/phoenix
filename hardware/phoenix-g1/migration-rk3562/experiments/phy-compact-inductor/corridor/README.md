# Corridoi PHY — variante sperimentale

PCB persistente: `pcb/phoenix-phy-corridor.kicad_pcb`, hash in `checkpoint.json`.
Non sostituisce il PCB autorevole o la BOM. Tutte le connessioni precedenti
sono preservate; nessuna nuova violazione DRC e nessun nuovo conflitto
meccanico nel confronto della revisione C517/terminazioni.

- C517 sul fronte a (62,2;27) mm, 0°.
- R511/R507/R512 sul retro, ancora senza percorso RGMII completo.
- C515 → C517: 1,05 mm sul fronte, senza via.
- Ritorno C515: 0,50 mm verso GND C1001, 2,604 mm contro 3,155 mm; vecchio
  ramo da 0,20 mm e relativo via sostituiti esplicitamente.
- Ritorno C511: da 0,20 a 0,50 mm; via originale conservato e secondo via
  0,45/0,20 a (58,85;31,625). Prima posizione 31,7 respinta: distanza fori
  insufficiente. Nessuna regola di foratura allentata.

Cinque test isolati superati: continuità ingresso/masse, interruzione ingresso,
rifiuto restringimento ingresso e masse, larghezze effettive dei ritorni.
Usare Python KiCad 10 con `tools/test_phy_corridor_study.py` (sotto phoenix-g1).

Restano aperti nodo SW, alimentazione a monte e distribuzione ai carichi 1 V.
Il fanout stretto già presente ai pin non è qualificato per la corrente
principale. Restano SI/PI, ripple, stabilità, termica e verifica fisica.
Nessun nuovo componente rispetto allo studio compatto; la sua BOM resta
sperimentale, con i limiti di sourcing e DCR già documentati.
