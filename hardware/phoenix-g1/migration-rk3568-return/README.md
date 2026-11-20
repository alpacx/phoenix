# Ritorno a RK3568

Autorizzato il 18 novembre 2026. Baseline storica estratta senza sovrascrivere il lavoro RK3562. Nessuna migrazione elettrica completata: non utilizzare questa baseline per ordinare PCB.

Requisiti: Ethernet Gigabit full duplex, USB3 device verso Mac e Wi-Fi PCIe utilizzabili contemporaneamente. Wi-Fi vicino al gigabit è un obiettivo di throughput utile, non full duplex radio. VPN da misurare separatamente. Display, espansione, eMMC e raffreddamento passivo restano requisiti; ingombro da riverificare.

RAM: la scheda RK3562 implementa 1 GiB LPDDR4; lo studio 512 MiB non ha ancora prodotto una sostituzione qualificata. Il vecchio design-target.json riportava 512 MiB ma non corrispondeva all’implementazione.

La baseline RK3568 precede le modifiche eMMC, espansione, meccaniche e di routing: recuperare tali blocchi dal checkpoint RK3562 verificando piedinatura e rail. Non copiare automaticamente il rame.

Sequenza: inventario schema/PCB e librerie della baseline; assegnazione USB3/PCIe/GMAC; scelta radio con driver AP e sourcing; budget alimentazione/RAM; integrazione schemi; disposizione e routing; verifiche CAD, SI/PI/termiche e prototipo.
