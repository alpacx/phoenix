# Regolatore di sistema 3,3 V — checkpoint locale

Il puntatore `working-candidate.json` identifica il PCB verificato. Deriva da
`../startup-power/working-candidate.json`; il progetto conserva RK3562, LPDDR4,
eMMC e le altre funzioni. Nessun componente, valore o MPN è stato cambiato.

## Interventi

- U17 TPS62132 mantiene posizione, orientamento e abilitazione Wi-Fi power-good.
- L1301 ruotato; C1301/C1302/C1303 sul retro; R1301 riposizionato.
- Tre terminali SW collegati all'induttore; tre VIN ai bypass locali; masse al
  pad esposto e piano di massa; uscita a C1304/C1305.
- SS/TR, PG e VOS collegati. VOS usa una derivazione di misura dal condensatore
  d'uscita, separata dal percorso di corrente. Il ritorno di C1303 scende
  direttamente al piano GND, senza il precedente lungo percorso di prova.
- Ingresso collegato al tronco +5V_MAIN esistente su In3.Cu, con pista da 1 mm.
- Un segmento CC_VBUS_SERIES_2 è sostituito da un percorso con gli stessi
  estremi per consentire l'uscita VOS. L'audit verifica la continuità precedente,
  non soltanto il nome della rete. Il resto del rame della baseline è conservato.

## Verifiche

90 coppie obbligatorie, incluse le 64 ereditate da CPU/PMIC/display; 2006 pad
conservati; nessuna nuova violazione DRC rispetto alla baseline. I test negativi
rimuovono SYS_SW e SYS_SS su copie in memoria e richiedono il rifiuto dell'audit.
L'inventario fisico conta 234 reti multi-pad ancora aperte: la linea di sistema
non raggiunge ancora gli ingressi PMIC. Il rail CPU resta separato dal +5V_MAIN.

Eseguire con il Python distribuito con KiCad, dalla root:

```
python hardware/phoenix-g1/tools/place_system_3v3.py
python hardware/phoenix-g1/tools/route_system_power.py
python hardware/phoenix-g1/tools/route_system_control.py
python hardware/phoenix-g1/tools/route_system_input_feed.py
python hardware/phoenix-g1/tools/audit_system_power.py
python hardware/phoenix-g1/tools/test_system_power_audit.py
python hardware/phoenix-g1/tools/inventory_stacked_connectivity.py --checkpoint hardware/phoenix-g1/migration-rk3562/experiments/system-3v3/working-candidate.json
```

## Limiti elettrici e produttivi

Il datasheet locale `reference/tps62130.pdf`, sezione 11.1, richiede percorsi
corti per i loop switching, VOS separato dal percorso di potenza e AGND/PGND
collegati al pad esposto. Il presente risultato verifica la geometria e la
continuità, non stabilità, transitori, EMI, portata delle piste/via, derating dei
condensatori o temperatura. La derivazione VOS è circa 16 mm, compresi gli
escape: da riesaminare nella compattazione del layout. I bypass sul retro e i
via nel pad esposto richiedono revisione di fabbricazione/assemblaggio.

Non è stata eseguita simulazione elettrica né prova fisica; non è un progetto
pronto all'ordine. Dimensione PCB ancora 90×40 mm; target 85×35 non dimostrato.
La disponibilità JLCPCB non è stata riverificata in questa fase: nessun nuovo
MPN introdotto e nessuna disponibilità corrente dichiarata.
