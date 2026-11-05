# Architettura attuale

ESP-IDF/lwIP con esp-netif Ethernet e un driver esp-netif USB custom.
USB è una LAN instradata con DHCP e NAPT, non un bridge trasparente.
Il core C portabile esegue parsing IPv4 e regole ordinate (max 32), direzione,
interfaccia, subnet, protocollo, intervallo porta destinazione, allow/deny.
Default deny nel motore; regole iniziali: HTTP locale USB e inoltro USB dopo gate.

Il hook IP4_INPUT precede NAT e consegna locale. Scarta IPv6 (anche disabilitato
nello stack), VLAN, frammenti IPv4, opzioni IP, protocolli fuori TCP/UDP/ICMP,
source spoofing USB e traffico di gestione dall'uplink. Sull'uplink il traffico
di ritorno deve essere destinato all'indirizzo dell'interfaccia; NAPT riscrive
soltanto flussi esistenti. Nessun port forwarding. Il connection tracking
attuale è quello NAT, non un firewall TCP stateful completo.

WireGuard espone una netif IPv4 separata. Routing per sorgente USB verso WG
quando la VPN è obbligatoria; NAPT riscrive l'indirizzo client nell'indirizzo
VPN. Datagrammi esterni WireGuard sono vincolati esplicitamente a Ethernet,
mai alla route del tunnel. Chiavi/sessioni/keepalive/rekey sono della libreria.
MSS clamp su SYN e SYN-ACK preserva l'MTU del tunnel. UDP grandi, frammentazione
e PMTU richiedono ancora test; i frammenti in ingresso sono sempre scartati.

Tre punti di blocco: input, canforward e linkoutput Ethernet. Senza modalità
diretta quest'ultimo permette soltanto ARP, DHCP locale e UDP dell'endpoint
WireGuard attivo. Transizioni sotto lock lwIP, NAT e code ARP svuotate prima
di cambiare percorso. Frame già consegnati al DMA non possono essere revocati.
Nessuna prova di assenza leak può essere dedotta dai soli test del motore.

Il clock deve essere impostato via seriale prima del tunnel; nessuna richiesta
NTP/DNS esterna di bootstrap. DRBG inizializzato con entropy hardware P4 tramite
bootloader_random_enable; ADC non usato da altri moduli. OTA non implementato:
sono predisposte due partizioni e rollback, ma non esiste un uploader né una
chiave di firma inventata. Secure boot/flash encryption restano disattivati.

USB copia buffer e usa invio sincrono con timeout, scelta prudente finché non
sono misurate pressione memoria e prestazioni. La variante async upstream 2.0.1
contiene una dereferenziazione precedente al controllo calloc e non è usata.
UI e pairing sono task separati; nessun interprete di codice arbitrario.
