> **Superato dalla decisione successiva dell’utente:** proseguire con la scheda RK3562 attuale. Questo documento resta uno studio, non un requisito di refactor attivo.

# Wi-Fi gigabit — requisito aggiornato 18 novembre 2026

Richiesta utente: Wi-Fi capace di raggiungere il gigabit, con miglior rapporto costo/prestazioni. Interpretazione prudente: throughput utile vicino al limite Ethernet Gigabit, non sola velocità PHY nominale e non somma delle bande. La VPN richiede una misura distinta.

AP6256 non soddisfa il requisito; il CAD esistente resta checkpoint storico, non una selezione valida per questo nuovo obiettivo. Nessuna sostituzione elettrica applicata.

## Vincolo di architettura

RK3562 condivide la combo PHY fra USB3 e PCIe. USB3 device verso Mac deve restare disponibile. SDIO SDR104 4 bit ha limite lordo 832 Mbit/s; un upgrade SDIO non soddisfa gigabit utile. Un hub USB non permette al medesimo controller di essere contemporaneamente device verso Mac e host verso una radio.

Fonte Rockchip: https://rockchip.fr/RK3562%20datasheet%20V2.1.pdf
Conferma produttore scheda: https://docs.forlinx.net/rockchip/ok3562j-c/OK3562J-C_User_Hardware_Manual.html

## Shortlist, non scelta qualificata

- MediaTek MT7922: Wi-Fi 6/6E 2x2, 160 MHz, PCIe; candidato compatto. Supporto AP 160 MHz aggiunto al driver Linux: verificare kernel effettivo, firmware, dominio regolatorio/DFS e client. Prezzo e disponibilità JLC non confermati.
- MediaTek MT7916 su modulo AsiaRF AW7916: soluzione orientata AP, da confrontare per costo, dimensioni, consumo e antenne. Non ancora qualificata per ingombro Phoenix né sourcing JLC.
- AP6275S: prezzo precedentemente verificato $12.462, ma bus SDIO incompatibile con obiettivo gigabit utile. Non selezionare solo per etichetta Wi-Fi 6.

Fonti:
https://lists.infradead.org/pipermail/linux-mediatek/2025-June/093889.html
https://asiarf.com/product/wi-fi-6e-mini-pcie-module-mt7916-aw7916-npd/
https://asiarf.com/wp-content/uploads/2023/09/AW7916-NPDV1.pdf

Prima della modifica CAD: individuare SoC con USB3 device e PCIe indipendenti, verificare costi complessivi (non solo radio), DDR/PMIC e footprint; qualificare due catene RF/antenne. Preferenza progettuale Wi-Fi 6 2x2 160 MHz per margine PHY, non requisito universale per qualsiasi implementazione gigabit. Validare in AP con iperf3 verso Ethernet, poi VPN separata. Nessuna garanzia di gigabit su qualsiasi telefono o canale.
