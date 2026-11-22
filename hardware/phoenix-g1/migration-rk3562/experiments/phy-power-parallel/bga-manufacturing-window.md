# Uscita delle sfere interne RK3562

Sul PCB a sei strati da 1,60 mm tre sfere isolate hanno otto land di altre reti disposti su un anello a passo 0,50 mm. Sono U1.AF25 (XOUT24M), U1.AF26 (USB_DM) e U1.AE26 (ADDON_USB_DM). Il rapporto contiene contrassegni e reti degli otto vicini di ogni sfera. È un limite inferiore. [Verifica geometrica](bga-closed-escape-rings.json)

Con land da 0,25 mm, pista da 0,20 mm e persino la clearance locale di 0,0762 mm prevista dal file di progetto, i dischi di esclusione dei pad consecutivi si sovrappongono di 0,1024 mm. La pista di superficie resta all’interno dell’anello. Per evitare la sovrapposizione di una via da 0,45 mm al land, il centro del foro deve distare almeno 0,35 mm dal centro della sfera. In questa regione il vicino più prossimo dista al massimo 0,356 mm. Il foro da 0,20 mm richiede invece 0,475 mm fra il suo centro e quello del pad vicino per rispettare la distanza foro-rame di 0,25 mm.

## Prova su copie del PCB

Sono state inserite tre vie passanti riempite e ricoperte, centrate sulle tre sfere, mantenendo tutte le regole, riempiendo nuovamente i piani e ricaricando ogni copia. I Gerber di prova misurano separatamente rame, maschera e pasta. [Risultati CAD](bga-filled-via-process.json)

| Grandezza nominale | Via ordinaria del progetto | Esempio BGA pubblicato da JLCPCB |
|---|---:|---:|
| Foro / rame della via | 0,20 / 0,45 mm | 0,15 / 0,25 mm |
| Anello nominale | 0,125 mm | 0,050 mm |
| Rapporto fra spessore e foro | 8,00 | 10,67 |
| Rame sul centro del pad dopo l’unione | 0,45 mm | 0,25 mm |
| Apertura maschera / pasta nel Gerber | 0,25 / 0,25 mm | 0,25 / 0,25 mm |
| Margine radiale fra rame e bordo nominale della maschera | 0,10 mm | 0,00 mm |

Il foro e il rame da 0,45 mm appartengono a due geometrie distinte. Sul primo coupon il rame sporge di 0,10 mm per lato e l’apertura resta da 0,25 mm. La geometria del giunto dipende anche dalla registrazione reale della maschera e dal processo di planarizzazione. Le tre vie alterano i piani di ritorno In1/In4. Sul secondo coupon il primo rame GND campionato dista almeno 0,33 mm dal centro delle vie. Il tronco +3V58_WIFI su In3 e il pad di C1635 sul retro interferiscono con i siti proposti sul PCB esaminato. Le misure campionano sedici direzioni; i percorsi USB completi richiedono verifica dell’impedenza e del ritorno.

## Fabbricazione e costo

JLCPCB mostra la soluzione da 0,15/0,25 mm in un esempio specifico a passo 0,50 mm e nella stessa pagina suggerisce un land da almeno 0,35 mm quando possibile. Il profilo Phoenix corrente prescrive foro minimo da 0,20 mm, rame della via da 0,45 mm e anello da 0,10 mm. Il secondo coupon segnala tutte e tre le incompatibilità. La tabella di processo ammette 0,15/0,25 mm sui multistrato e indica un sovrapprezzo per fori da 0,15 mm. Associa ENIG ai land BGA da 0,20–0,25 mm e dichiara una tolleranza generale di posizione foro di ±0,075 mm. Questo dato non garantisce, da solo, un anello residuo da 0,050 mm sul processo specifico. La disponibilità della resinatura per schede a sei strati da sola non determina il costo del foro piccolo, la tolleranza di registrazione o l’idoneità allo specifico stackup. [Guida BGA JLCPCB](https://jlcpcb.com/help/article/bga-design-guidelines---pcb-layout-recommendations-for-bga-packages) · [Capacità di fabbricazione](https://jlcpcb.com/capabilities/pcb-capabilities) · [Guida POFV](https://jlcpcb.com/help/article/via-in-pad-pofv-guide)

Una microvia cieca da 0,10 mm con land da 0,25 mm è un’alternativa di processo. Sul progetto In1 è un piano GND. Una via F–In1 per segnali richiede una finestra nel piano e un percorso appropriato verso un layer segnali. La configurazione HDI, il numero di laminazioni e l’extra costo richiedono un preventivo per quello stack. La conferma di fabbricazione deve comprendere spessore 1,60 mm, sei strati, foro, rame, metallizzazione, registrazione dopo foratura e maschera, anello residuo minimo, finitura e tolleranza del cap. [Capacità HDI JLCPCB](https://jlcpcb.com/pcb-fabrication/hdi-pcb)

Entrambi i coupon restano separati dal layout accettato.
