# Ripresa hardware — pausa per banco ROCK USB, 15 novembre 2026

Checkpoint: `working-candidate.json`, PCB `pcb/vdc-passives.kicad_pcb`.
SHA256: 53fc6a05acd6c0fe6c2204486a6397a5b38e68d2b9bc65a77a12916b69831160.
Audit completato: 117 coppie, 18 test passati, nessuna nuova violazione DRC.
Inventario: 233 reti multi-pad aperte. +3V3_SYS distribuita dalla sorgente U17;
VCC9/VCC8 collegati, TP4 spostato e R410 alimentato. R410/R411/C410 avvicinati
e collegati localmente; U4.61 (VDC) resta aperto. Nessuna prova di accensione.
Nuovi script, dopo route_pmic_vcc4_input.py:
- route_pmic_vcc9_link.py (ora accettato: supera il precedente tentativo rifiutato)
- route_system_pmic_feed.py
- route_pmic_vdc_input.py
- route_pmic_vdc_passives.py

Via-in-pad C425/C481 e C1304/C1305: richiedono riempimento e copertura POFV;
vedere pcb/via-in-pad-process-review.json e fonti JLCPCB. Nessun ordine approvato.
Bus 3V3 da 0,8 mm e via sorgente paralleli: portata/caduta di tensione/temperatura
non qualificate, stackup finale da confermare. Non è produzione pronta.
README storico ancora da riconciliare: i riferimenti a vcc9-link rifiutato e a
U17 separato descrivono fasi precedenti. Fa fede questo checkpoint con hash.
Nessun commit/push richiesto o effettuato. Lavoro CAD sospeso su richiesta utente.
