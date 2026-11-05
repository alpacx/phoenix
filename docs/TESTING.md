# Piano di prova riproducibile

## Host

`./tools/test.sh`: clang + UBSan, core C, corpus deterministici. Non valida
hardware, lwIP completo o crittografia. ASan ha un problema runtime locale anche
su programma vuoto; non segnarlo PASS. Su altro host riprovare aggiungendo address
ai sanitizer. Registrare compiler/versione e output.

## Scheda

1. Identificare revision/flash_id e salvare intera flash prima di aggiornare.
2. Build revisione corretta, USB off; flash, log boot senza panic, Ethernet PHY
   detect/link/DHCP e 30 minuti di heap stabile. Ripetere stacco/riattacco Ethernet.
3. Solo dopo verifica elettrica fixture, build lab corretta e enumerazione NCM su
   Mac. Annotare macOS/versione, velocità USB negoziata, lease e route.
4. Pair via seriale; GET status senza token deve rispondere 401, con token 200.
   POST mode invalido 400, Origin esterna 403. Da uplink porta80 inaccessibile.
5. Default chiuso, nessuna navigazione; direct esplicito: iperf3 TCP entrambe le
   direzioni e UDP, DNS UDP/TCP. IPv6/VLAN/frammenti e spoof sorgente bloccati.
6. Server WireGuard locale o profilo utente. Impostare ora, importare profile,
   verificare handshake reale e IP di uscita del CLIENT, non solo della P4.
7. Cattura su uplink con tcpdump: VPN mandatory deve mostrare solo ARP/DHCP e
   endpoint WireGuard per traffico prodotto dal dispositivo. Inviare dal client
   DNS/TCP/UDP e IPv6 durante avvio, tunnel down, server switch, cavo rimosso,
   USB detach/suspend/resume. Verificare anche code ARP pendenti al cambio mode.
8. Misurare file grandi, MSS, UDP vicino MTU, ICMP unreachable/PMTU e reconnessione.

Nessuno script deve cambiare automaticamente route/interfacce del Mac.
Per iperf3 sul client: `iperf3 -c <IP_SERVER_LAB> -t 60 -J`, poi aggiungere `-R`.
Per cattura: `tcpdump -ni <INTERFACCIA_DI_CATTURA> -w <RISULTATO.pcap>`;
selezionare manualmente l'interfaccia del banco. Non usare reti/dispositivi estranei.

## Registro prestazioni

Per ogni modalità (USB-Ethernet, firewall, firewall+WG, AP+WG) registrare commit,
config, alimentazione, silicon revision, MAC OS, endpoint locale, MTU, direzione,
stream, durata, throughput utile, RTT mediana/p95, heap minimo/finale, CPU e reset.
Ripetere 3 volte e almeno un soak di 8 ore. Tutti questi risultati sono MANCANTI.
Test OTA interruzione alimentazione da eseguire solo quando OTA firmata è implementata.
