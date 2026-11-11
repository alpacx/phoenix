# Aggiornamenti applicativi firmati

Implementazione di ingegneria. Firma Ed25519 reale, hash del payload, sequenza
monotona persistente, staging privato, switch atomico e rollback. Non aggiorna
kernel, bootloader, unità systemd o bootstrap; non equivale a secure boot.
Un amministratore root può modificare chiave e stato: il modello non protegge
contro un target già compromesso con accesso root.

## Prima installazione

Identificare modello e interfacce, preparare target.json come in README.md.
Il bundle iniziale deve arrivare da una sorgente fidata via SSH: il suo manifest
è un checksum, non una firma. Il programma rifiuta modelli diversi e directory
di installazione preesistenti. Sul target identificato, da un checkout fidato:

```sh
sudo env PYTHONPATH=platforms/linux/service python3 -m phoenix_linux.install \
  --bundle /percorso/phoenix-linux.zip --target-config /percorso/target.json \
  --public-key /percorso/update-public.pem
```

L'installatore copia soltanto la chiave pubblica di firma e genera separatamente il certificato TLS locale. Non avvia servizi e non cambia
la rete. Crea /opt/phoenix-releases/factory, symlink /opt/phoenix, bootstrap
indipendente in /opt/phoenix-bootstrap, configurazione privata /etc/phoenix e
le quattro unità. Omettere --public-key disabilita gli aggiornamenti nel pannello.
Non eseguire questa installazione sul Mac.

Dopo verifica della configurazione e prova foreground descritta in README:

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now phoenix.service
```

## Chiave del produttore e release

Creare una chiave di firma privata OFFLINE, fuori dal repository, proteggendola
con permessi 0600 e backup sicuro. Non generarla sul gateway. Per una chiave
Ed25519 OpenSSL: `openssl genpkey -algorithm ED25519 -out /percorso/privato.pem`;
esportare la sola pubblica con `openssl pkey -in /percorso/privato.pem -pubout
-out /percorso/update-public.pem`. Impostare prima `umask 077`.

Dalla root del checkout, con destinazioni non ancora esistenti:

```sh
PYTHONPATH=platforms/linux/service python3 -m phoenix_linux.package build /tmp/phoenix-linux.zip
PYTHONPATH=platforms/linux/service python3 -m phoenix_linux.updates sign \
  --payload /tmp/phoenix-linux.zip --output /tmp/phoenix-release.phx \
  --key /percorso/privato.pem --sequence 1 --version 0.1.0
```

Lo staging richiede spazio per il payload espanso più 64 MiB liberi di riserva.
Incrementare sequence per ogni distribuzione, anche dopo un rollback. Non viene
usata la comparazione lessicografica di version. Il pacchetto interno unsigned
è autenticato dall'hash nei metadati firmati dell'involucro .phx. Limite 20 MiB.
La firma è verificata contro la chiave già installata, mai una chiave caricata.

## Attivazione e recupero

Sistema → Aggiornamento software, visibile solo se configurato. La firma viene
verificata prima del blocco del traffico; dopo lo staging si fermano ritentativi
e nuovi comandi. L'updater separato ferma frontend e worker, cambia symlink, li riavvia e
controlla /healthz via HTTPS sulla loopback per massimo 30 secondi, inclusa identità della
release. Se fallisce torna alla precedente. Questa prova controlla l'avvio del
servizio, NON navigazione, radio, VPN, performance o compatibilità dei dati.
Il gateway riparte bloccato: riconnettere esplicitamente la VPN dal pannello.

La recovery viene eseguita prima del servizio al boot e dopo un fallimento
dell'updater. Uno switch interrotto torna alla precedente release. Il bootstrap
resta indipendente dal codice applicativo sostituito. Conservare le release
precedenti; nessuna garbage collection automatica di versioni in questa build.
Gli schemi SQLite devono restare compatibili con la release di rollback.

Se systemd non riceve il comando dopo lo staging, il gateway rimane bloccato.
Da SSH: `sudo systemctl start phoenix-update.service` riprende lo staging.
Stato in /var/lib/phoenix/update-state.json; non contiene credenziali. Se la fase
è rollback_failed, recuperare da SSH/console: non abilitare la rete alla cieca.

Test automatizzati: firme vere OpenSSL, alterazioni, chiave errata, replay,
rollback, interruzione e upload HTTP. In VM Debian: frontend non root, upload HTTPS,
attivazione sotto systemd reale, rollback da release non avviabile e recupero
del journal dopo reboot reale. Power loss durante I/O e storage della ROCK
restano prove sul banco. Le unità/bootstrap modificati richiedono installazione
iniziale aggiornata: un vecchio deployment monoprocesso non viene convertito
automaticamente da un aggiornamento applicativo.

Riferimento: https://docs.openssl.org/3.1/man1/openssl-pkeyutl/
