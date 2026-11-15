# Ripresa hardware — 15 novembre 2026

Checkpoint: `working-candidate.json`, PCB `pcb/five-volt-testpoint.kicad_pcb`.
SHA256: f190cccb41316252dd914775db16d4c3fc46737564beff8728ea24a00eb9bb52.
Audit: 119 coppie, 20 test; nessuna nuova violazione DRC.
Ultimi stadi: route_cpu_input_feed.py, route_five_volt_testpoint.py.
Ingresso CPU +5V_MAIN e TP3 collegati; nessun cambio componenti o footprint.
Resta aperto U4.61 VDC, R1803.1, uscita CPU verso SoC e altre reti.
Nessuna qualifica corrente/temperatura/stackup o prova fisica. Vedere README.
Checkpoint precedente pubblicato con fbcb7de su origin/master, account alpacx;
account GitHub ripristinato a Coqoonit dopo push. Nuova continuazione locale.
ROCK USB e hotspot ora provati; vedere BRINGUP software per stato e limiti.
Non riavviare o modificare il target fisico per queste attività CAD.
