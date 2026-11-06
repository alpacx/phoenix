# NordVPN direttamente sul P4

Requisiti confermati il 6 novembre 2026:

- Il tunnel WireGuard verso NordVPN termina sul P4. Il Mac non è un relay, un exit node o un requisito per la rotazione.
- Un paese selezionato è un vincolo, non una preferenza. Durante la rotazione si scelgono solo server di quel paese. Se nessuno è disponibile, il traffico rimane bloccato e il pannello mostra il motivo.
- Nessun paese selezionato: scelta casuale del paese e quindi del server tra le destinazioni disponibili. Si esclude il server corrente se esiste un'alternativa ammissibile.
- La rotazione è disattivata inizialmente; l'intervallo viene configurato in secondi. Il timer decorre dalla connessione riuscita, non dall'avvio di un tentativo. Un tentativo fallito non deve creare un ciclo di riconnessioni senza attesa.
- Durante handshake, cambio server, riavvio o errore non deve esserci fallback a Internet diretto.
- Le connessioni applicative possono interrompersi al cambio server. Un server diverso non garantisce un IP pubblico diverso.
- La UI deve distinguere account configurato, catalogo disponibile, tunnel in connessione, tunnel con handshake riuscito e IP di uscita effettivamente verificato. Nessuno stato simulato.
- L'account desktop NordVPN sul Mac non configura automaticamente il P4. Non si estraggono credenziali dall'app installata. Il percorso di provisioning deve usare credenziali/configurazioni esplicitamente fornite al dispositivo.

## Implementazione attuale

Il gestore in `main/vpn_manager.c` esegue provisioning HTTPS, selezione del server,
persistenza NVS, connessione WireGuard e scheduler direttamente sul gateway.
L'access token fornito nel pannello viene scambiato con la chiave WireGuard e
scartato; le risposte API non espongono chiavi. La chiave resta in NVS; la build
di sviluppo non abilita flash encryption.

Il catalogo compilato contiene 150 paesi; le raccomandazioni dei server sono
richieste in tempo reale. In modalità casuale il paese precedente è escluso
quando esistono alternative. Con un paese fissato non esiste fallback geografico.
L'intervallo accettato è 30–86400 secondi e parte dal tunnel connesso.
Se la rotazione è spenta, la scelta casuale avviene solo alla connessione o al
comando manuale. Le modifiche si applicano con «Salva e connetti».

L'accesso amministrativo locale sul Mac usa `tools/admin_bridge.py` e la UART:
`http://127.0.0.1:8085`. Il bridge serve la UI e inoltra richieste agli stessi
handler HTTP autenticati del gateway; non trasporta il traffico Internet.
Dall'hotspot il pannello è disponibile su `http://192.168.9.1` con token admin.
La UI non dipende dal modello hardware. Il tunnel NordVPN non usa il Mac come relay.

Il firewall e le mappature porte persistono separatamente dal profilo VPN.
Le mappature locali non abilitano porte in ingresso sui normali server NordVPN.
La modalità diretta è una scelta esplicita persistente, mai un fallback.

Test host: vincolo geografico, cataloghi vuoti, esclusione del paese precedente
su 150 destinazioni e 100000 valori casuali, policy e validazione WireGuard.
Handshake NordVPN reale e persistenza delle credenziali attraverso il riavvio
verificati. I risultati della prova di rotazione sono nel file locale
`results/gatewaybench/rotation-live.log`; non contiene credenziali.
