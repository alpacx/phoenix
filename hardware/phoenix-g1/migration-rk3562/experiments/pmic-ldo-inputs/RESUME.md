# Ripresa hardware — 16 novembre 2026

Fonte: `working-candidate.json`, percorso e SHA256 correnti.
PCB `pcb/ethernet-clock-pins.kicad_pcb`: 172 coppie, 51 test CAD passati,
nessuna nuova violazione DRC. Test aggiuntivi: rollback e interferenza H8105.
Dalla root, Python KiCad + `hardware/phoenix-g1/tools/rebuild_local_copper.py`.
Sono sedici stadi dopo five-volt-testpoint. README documenta regola aggiunta,
misure geometriche, prove e limiti. Nessuna modifica ROCK.

Y501/C520/C521 riposizionati; L501 spostato sul retro. Quarzo, condensatori,
masse e due pin PHY collegati. H8105 liberato da Y501. 19 possibili interferenze
meccaniche preesistenti ancora aperte; leggere mount-component-screen.json.
Nessuna connessione precedente persa. R513 tentata ma non spostata; RSET aperta.

227 reti multi-pad aperte. PMIC, escape USB/eMMC, alimentazioni PHY (L501 incluso),
SI/PI, avvio, termica, EMC/DFM e DS1 restano da completare/qualificare. I 13 pad
del display non sono presenti. PCB 90×40 mm, obiettivo 85×35 non validato.
Nessun ordine, commit/push o prova fisica in questa prosecuzione.
