# Phoenix 80 × 30 mm — verifica preliminare, 10 novembre 2026

Esito: fattibilità condizionata, non dimostrata per una scheda funzionante. Nessuna modifica alla scheda principale.

La prova usa gli ingombri dei footprint del candidato PMIC, escludendo J3. La disposizione rettangolare a due lati colloca 268/352 footprint su 76 × 26 mm con margine addizionale 0,25 mm; la variante ottimistica 78 × 28 mm senza quel margine colloca 352/352. Le due prove variano sia dimensioni sia margini: non isolano il contributo di ciascuna modifica. Non rispettano raggruppamenti elettrici dei passivi, timing DDR, ritorni, RF, termica o altezze. Un fallimento non prova impossibilità, un successo non dimostra un PCB instradabile. Il formato esterno resta un obiettivo, non una promessa.

## Display e costi

- Display attuale N096-1608TBBIG11-H13: 27,95 × 13,5 × 1,5 mm, 160 × 80, JLC C2890616, 1,8359 USD; quantità ordinabile osservata 328, minimo 5.
- Comando TM-4175-B-A: corpo 7,5 × 7,5 mm, JLC C465995, 0,7969 USD; quantità ordinabile 609, minimo 14. Cappuccio e sostegno meccanico esclusi.
- Totale componenti sopra: 2,6328 USD, non un preventivo assemblato.
- Waveshare 1.47inch Touch LCD: 41,69 × 22,05 mm, 320 × 172, SPI + I²C, JD9853 + AXS5106L; 11,99 USD, InStock osservato direttamente sul sito. Fornitura/assemblaggio JLC non confermati.
- Waveshare 1.47inch LCD Module non touch: 38,5 × 22 mm, 9,99 USD; con comando 10,7869 USD. Il sovrapprezzo del touch a pari diagonale è circa 1,20 USD prima di accessori e assemblaggio.
- Waveshare 1.69inch Touch LCD Module: 33,13 × 41,13 mm, incompatibile con larghezza esterna 30 mm.

Fonti: https://jlcpcb.com/partdetail/C2890616 ; https://jlcpcb.com/partdetail/C465995 ; https://www.waveshare.com/1.47inch-touch-lcd.htm ; https://www.waveshare.com/wiki/1.47inch_Touch_LCD ; https://www.waveshare.com/1.47inch-lcd-module.htm ; https://www.waveshare.com/1.69inch-touch-lcd-module.htm ; datasheet locale reference/display-C2890616.pdf.

La tavola ui-envelope-comparison mostra solo la faccia superiore. Supporti, flessibili, antenna, dissipatore, volume dei connettori e protezione del display restano da verificare. Lato software non è stato provato il driver Linux sul nostro RK3562. Esclusi tasse, trasporto, minimi, eccedenze, assemblaggio, cablaggi e costi dell'involucro.

Scelta preliminare: 0,96″ + comando per risparmio massimo; touch 1,47″ per leggibilità e comandi senza sporgenze. Nessuna necessità di abbinare touch e joystick per i menu previsti. La dissipazione dovrebbe essere studiata verso fondo/lati, evitando di usare il display come percorso termico; è una proposta non simulata.
