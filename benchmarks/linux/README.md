# Banco prestazioni Linux

Usare una cartella distinta per ogni sessione e fase in results/. Conservare i JSON client di iperf3 e il CSV della ROCK insieme. Il nome della fase deve indicare il percorso (idle, USB diretto, gateway Ethernet, gateway VPN, carico prolungato, recupero). Per il confronto 512 MiB usare una sessione distinta. Registrare release installata, RAM visibile, kernel, link negoziati, topologia, temperatura ambiente e dissipatori. I JSON grezzi di iperf possono contenere IP locali.

Esempio dalla root sul Mac con alias SSH già configurato e indirizzo del peer di test in PEER. Verificare prima che la route al peer attraversi Phoenix. Il peer deve già eseguire iperf3 in modalità server. Il comando SSH esegue il campionatore sulla ROCK senza installarlo.

    phase=results/linux-bench/session-01/vpn
    mkdir -p "$phase/raw"
    ssh "$ROCK" python3 - 110 < benchmarks/linux/sample.py > "$phase/raw/rock.csv" &
    sampler=$!
    iperf3 -c "$PEER" -P 4 -t 30 -J > "$phase/raw/upload.json"
    iperf3 -c "$PEER" -P 4 -R -t 30 -J > "$phase/raw/download.json"
    iperf3 -c "$PEER" -P 4 --bidir -t 30 -J > "$phase/raw/duplex.json"
    wait "$sampler"
    python3 benchmarks/linux/report.py "$phase/raw" "$phase/report" --context 'Riportare release, topologia, ambiente e condizioni effettive'

Per lo stato di riposo basta il CSV. Per una prova sostenuta aumentare insieme durata del carico e del campionamento. Ripetere per ogni configurazione; il grafico riporta i singoli test. Il report richiede matplotlib sul computer di analisi; il campionatore utilizza la sola libreria standard Python su Linux. Conservare le interpretazioni manuali in un file separato dal debrief.md rigenerabile.

## Confronto USB, hotspot e carico simultaneo

Usare la stessa VM Oracle e registrare build, banda della VM, interfaccia, paese/server VPN, temperatura ambiente, canale, RSSI e velocità radio negoziata. Verificare l'IP sorgente osservato dalla VM per ogni modalità. Per usare un solo Mac, collegare il Wi-Fi a Phoenix-Test e mantenere USB collegata. Vincolare ciascun processo iperf3 alla sua interfaccia con --bind-dev e verificare sul gateway i byte su wlan0 e phusb0. Un telefono con dati mobili disattivati è un client alternativo. Per ogni condizione acquisire una sola telemetria della ROCK a 1 Hz e salvare i dati iperf3 separatamente per ogni client.

| Ordine | Percorso | Uscita |
|---|---|---|
| 1–3 | USB solo, Wi-Fi solo, USB e Wi-Fi simultanei | Diretta |
| 4–6 | USB solo, Wi-Fi solo, USB e Wi-Fi simultanei | Stesso tunnel VPN |

Per la calibrazione su Mac eseguire flow_sweep.py con IP del peer, interfaccia attesa e directory nuova. Confrontare le mediane di tre repliche a 1, 4, 8, 16 e 32 flussi. Per il confronto scegliere lo stesso gradino e registrare i flussi per client. Nel confronto a pari carico dividere i flussi tra i due client (per esempio 8+8 rispetto a 16). Confrontare il totale e la banda ricevuta da ciascun client. Un eventuale test di saturazione a doppio carico va etichettato separatamente.

Ogni sessione sostenuta dura 30 minuti: 10 upload, 10 download, 10 bidirezionali. Registrare medie per minuto e picchi per core, RAM disponibile, swap, temperatura e frequenze. Attendere il ritorno alla temperatura iniziale tra sessioni; se nell'ultima fase la temperatura sale ancora, prolungare quella fase a carico costante. Per traffico simultaneo servono due istanze server iperf3 su porte distinte e avvii coordinati. Sul Mac verificare la route verso la VM prima di ciascuna fase; sul telefono usare un client iperf3 con reverse e bidirezionale e conservare i risultati. Una configurazione con un solo telefono misura una sola stazione radio.

### Suite locale su un solo Mac

Il server iperf3 si lega all’indirizzo Ethernet del Mac e il client alla USB o al Wi-Fi. La calibrazione del 22 novembre ha verificato il transito sulla ROCK tramite i contatori fisici. Non serve un host Internet. Per la configurazione di banco lanciare da macOS:

    python3 benchmarks/linux/direct_suite.py --rock radxa@192.168.7.1 --socket "$SSH_CONTROL_SOCKET" --ethernet en8 --usb en14 --wifi en0 --output "results/linux-bench/direct-$(date +%Y%m%d-%H%M%S)"

Usare un socket SSH autenticato e una cartella nuova. La suite assume le reti USB 192.168.7.0/24 e hotspot 192.168.9.0/24, canale 36. Esegue sweep da 15 s per gradino, upload e download, selezione del numero di flussi entro il 5% dal massimo osservato nella somma dei due sensi, confronto anche bidirezionale e simultaneo a pari budget, quindi 30 minuti costanti nella configurazione con CPU media più elevata e 60 s di recupero. La selezione è esplorativa e usa una prova per gradino. Il CSV registra le medie ricevute e gli intervalli JSON conservano la dinamica iperf. I ping vincolati misurano la latenza durante il carico. La telemetria viene scritta anche in locale sulla scheda. Per lavoro disconnesso usare un job macOS locale e mantenere il computer acceso.

Il peer VPN in wg-peer usa un container dedicato con NET_ADMIN solo nel proprio namespace, UDP 51873 sulla porta Ethernet del Mac e iperf3 su 10.77.51.1 (porte 25192–25193 interne). La prova check-path richiede la chiave effimera client in /run/phoenix-bench-wg sulla ROCK e il relativo peer già registrato nel container. Verifica l’handshake da un namespace temporaneo senza cambiare il percorso dei client della suite diretta.
