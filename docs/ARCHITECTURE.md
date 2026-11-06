# Architettura attuale

ESP-IDF/lwIP con esp-netif Ethernet e un driver esp-netif USB custom, più netif C6 STA/AP tramite ESP-Hosted.
USB è una LAN instradata con DHCP e NAPT, non un bridge trasparente.
Il core C portabile esegue parsing IPv4 e regole ordinate (max 32), direzione,
interfaccia, subnet, protocollo, intervallo porta destinazione, allow/deny.
Default deny nel motore; regole iniziali: HTTP locale USB e inoltro USB/AP dopo gate.

Il hook IP4_INPUT precede NAT e consegna locale. Scarta IPv6 (anche disabilitato
nello stack), VLAN, frammenti IPv4, opzioni IP, protocolli fuori TCP/UDP/ICMP,
source spoofing USB/AP e traffico di gestione dall'uplink. Sull'uplink il traffico
di ritorno deve essere destinato all'indirizzo dell'interfaccia; NAPT riscrive
soltanto flussi esistenti. Nessun port forwarding. Il connection tracking
attuale è quello NAT, non un firewall TCP stateful completo.

WireGuard espone una netif IPv4 separata. Routing per sorgente USB/AP verso WG
quando la VPN è obbligatoria; NAPT riscrive l'indirizzo client nell'indirizzo
VPN. Datagrammi esterni WireGuard sono vincolati esplicitamente all’uplink selezionato (Ethernet o STA),
mai alla route del tunnel. Chiavi/sessioni/keepalive/rekey sono della libreria.
MSS clamp su SYN e SYN-ACK preserva l'MTU del tunnel. UDP grandi, frammentazione
e PMTU richiedono ancora test; i frammenti in ingresso sono sempre scartati.

Tre punti di blocco: input, canforward e linkoutput Ethernet/STA. Senza modalità
diretta quest'ultimo permette soltanto ARP, DHCP locale e UDP dell'endpoint
WireGuard attivo. Transizioni sotto lock lwIP, NAT e code ARP svuotate prima
di cambiare percorso. Frame già consegnati al DMA non possono essere revocati.
Nessuna prova di assenza leak può essere dedotta dai soli test del motore.

Il clock deve essere impostato via seriale prima del tunnel; nessuna richiesta
NTP/DNS esterna di bootstrap. DRBG inizializzato con entropy hardware P4 tramite
bootloader_random_enable; ADC non usato da altri moduli. OTA autenticata con firma software RSA-3072: vedi [OTA](OTA.md). Due slot e
rollback; chiave di sviluppo locale riservata, mai nel repository. Secure boot
hardware e flash encryption restano disattivati.

USB copia buffer e usa invio sincrono con timeout, scelta prudente finché non
sono misurate pressione memoria e prestazioni. Il file network 2.0.1 è sostituito da un override locale per correggere
lifetime, callback ritardate e controllo calloc; dettagli in DEPENDENCIES.md.
UI e pairing sono task separati; nessun interprete di codice arbitrario.


C6: SDIO a 20 MHz, GPIO verificati sullo schema. Inizializzazione su richiesta;
scansione automatica solo nella build probe. STA e AP sono alternativi. Gestione
Wi-Fi serializzata; cinque retry, niente riconnessione al boot tramite credenziali
salvate senza comando esplicito. AP NAT su 192.168.9.1/24, un solo client. Il cambio
uplink/configurazione blocca e svuota gli stati, senza fallback diretto implicito.
Subreti uplink sovrapposte a USB o AP sono rifiutate. Il C6 di fabbrica accetta
le API di base provate; mancano metadati di versione e compatibilità estesa.
