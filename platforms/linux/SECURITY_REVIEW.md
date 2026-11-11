# Revisione locale software — 2026-11-11

Revisione interna del codice e delle prove, non audit indipendente o certificazione.
Ambito: frontend/API, RPC privilegiato, credenziali, policy e aggiornamenti.
Il deployment resta HTTPS loopback tramite SSH; non è esposto direttamente a Internet.

## Correzioni verificate

| Riscontro | Correzione / prova |
|---|---|
| RPC accettava JSON con chiavi duplicate e valori non finiti | Parser rigoroso comune a HTTP/RPC; test su entrambe le interfacce |
| Un flusso RPC lento poteva prolungare il timeout con letture parziali | Deadline complessiva di lettura di 20 secondi, senza rinnovo a ogni frammento |
| Header di autenticazione/Host/Origin duplicati erano ambigui | Rifiuto delle duplicazioni; regressione HTTP |
| Mancavano restrizioni browser esplicite | CSP, frame-ancestors, base-uri/object-src, form-action e Referrer-Policy; UI provata nei browser |
| Dopo una perdita precoce di una sessione confermata restava la finestra iniziale di handshake | Blocco e ritentativo immediatamente pianificati; test unitario e cicli reali Docker. Il firewall già impediva il fallback diretto |
| Logout non raggiungibile sul layout mobile e campo password Wi-Fi non ripulito | Logout in Sistema; cancellazione dei campi sensibili e del file WG selezionato; browser regression |
| Testi UI suggerivano ripartenza automatica e versione installata non distinguibile dal tentativo fallito | Testi coerenti con necessità di verificare/riconnettere dopo reboot e indicazione dell’ultimo pacchetto |
| Staging senza controllo preventivo dello spazio | Rifiuto se lo spazio libero non copre payload espanso più 64 MiB di riserva; stato e release corrente invariati nel test |

## Confini verificati

- Il frontend non ha capability né accesso diretto al vault; peer UID RPC verificato
  dal kernel. Non esistono operazioni RPC per comandi shell o file arbitrari.
- Token, chiavi VPN e password non sono restituiti dalle API o passati come argv.
  L’access token NordVPN non è persistito; la chiave derivata rimane nel vault privato.
- TLS verifica certificati e hostname; DNS/provisioning restano sull’uplink scelto,
  senza proxy/redirect o passaggio automatico a un’altra interfaccia.
- Aggiornamenti autenticati con chiave preinstallata, sequenza monotona, allowlist
  dei file, staging e rollback. Il frontend non sceglie comandi o percorsi di installazione.
- App e worker vengono fermati prima dello switch; crash/reboot verificati in VM.
- La UI usa escaping per contenuti dinamici e il token resta nella sessionStorage
  della scheda browser, eliminato al logout. Non è una protezione contro browser compromessi.

## Limiti residui

Un frontend compromesso può eseguire le operazioni amministrative consentite:
la separazione impedisce shell/file arbitrari, non revoca l’autorità amministrativa.
Root/attacco fisico può leggere il vault o modificare chiave e sequenza: niente
secure boot o cifratura del disco implementati. Python non garantisce azzeramento
delle stringhe sensibili in memoria. HTTP standard library è adatto a questo
banco locale, non a un servizio pubblico resistente a DoS. Gestione/rinnovo dei
certificati resta operativo-manuale. Le release vecchie vanno gestite senza
rimuovere quella corrente o di rollback; non c’è garbage collection automatica.

La prova prolungata è limitata a dieci minuti e traffico locale, non giorni di
uso né un audit crittografico. Nessuna prova con abbonamento NordVPN in questa
sessione: l’utente ha scelto di proseguire senza account reale. Non sono stati
estratti segreti da flash, Keychain o applicazioni NordVPN.
