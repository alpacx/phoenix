# Amministrazione web diretta sulla USB

Verificata sulla ROCK 4C+ il 15 novembre 2026, release applicativa firmata
`7-e5be66d837ffa82f` (0.1.0-rock7-password). Non cambia la qualifica elettrica
USB: valgono ancora i limiti in USB_ETHERNET.md.

Aprire **http://192.168.7.1**: porta 80, redirect fisso alla porta 443
**https://192.168.7.1/**. Non serve Wi-Fi o tunnel SSH. Per navigare su Internet
la ROCK richiede comunque un uplink e una VPN connessa, oppure uscita diretta
esplicitamente autorizzata. Il pannello locale non dipende dal tunnel VPN.

## Accesso

- Password iniziale `phoenix`; al primo login cambio obbligatorio, prima di
  leggere o modificare la configurazione. Nuova password: 12–128 caratteri.
- Tre password errate consecutive bloccano l'account per 300 secondi. Il
  blocco è globale, non aggirabile cambiando IP, ed è salvato su disco anche
  al riavvio. Vale anche per la verifica della password durante il cambio.
- Un login valido azzera il conteggio. Il cambio password revoca tutte le
  sessioni precedenti; Sistema → Cambia password permette modifiche successive.
- Sessione ordinaria: un'ora assoluta. Sessione limitata al primo cambio:
  dieci minuti. Logout e riavvio worker revocano le sessioni.
- Cookie `__Host-phoenix`: Secure, HttpOnly, SameSite=Strict, Path=/, nessun
  Domain. Nessun segreto di sessione in localStorage/sessionStorage o JSON UI.
- Hash scrypt con salt casuale in `/var/lib/phoenix/admin-password.json`,
  root-only 0600, aggiornamento atomico. Nessuna password in chiaro nei file.
- Il token tecnico precedente resta valido soltanto sul frontend loopback,
  per manutenzione e strumenti esistenti. Sulla USB non bypassa il login.
  Non confondere la password del pannello con le credenziali SSH.

La UI condivisa riconosce il supporto da GET /api/v1/auth/status. ESP32 e
backend legacy mantengono il login token: nessun cambio del protocollo ESP-IDF.

## TLS e isolamento

Certificato USB dedicato con SAN IP:192.168.7.1; chiave privata sul target
`/etc/phoenix/usb-admin-key.pem`, pubblico `usb-admin-cert.pem`. Il certificato
loopback precedente resta invariato. Verificare il certificato pubblico via
SSH autenticato prima di renderlo attendibile nel browser/portachiavi.
Non disabilitare la verifica TLS e non inserire password nella pagina HTTP.

Fingerprint SHA256 del certificato USB installato in questa sessione:
`0F:C4:32:07:2C:B1:F5:22:EA:73:ED:DE:61:6F:88:9B:F4:48:D8:D4:6F:85:3A:B1:08:71:E4:1D:E6:E4:39:56`.
La copia pubblica locale è `results/rock4c-plus/public/usb-admin-cert.pem`
(ignorata da Git). Non è una CA pubblica: il browser può richiedere fiducia
esplicita. Durata un anno; il rinnovo richiede ridistribuire la fiducia.

Unità opt-in `phoenix-usb-http.socket/.service` e
`phoenix-usb-https.socket/.service`. systemd crea i listener privilegiati con
ListenStream=192.168.7.1 e BindToDevice=phusb0; i processi girano come
phoenix-web senza capability. Il codice verifica indirizzo, porta, interfaccia,
numero di descrittori e PID prima di usare il socket ereditato. Non ascolta
su 0.0.0.0, Ethernet o hotspot. Nessuna modifica al firewall del Mac.

Le unità si installano separatamente dall'aggiornamento applicativo firmato,
che non modifica systemd. HTTPS richiede il worker e segue gli arresti del
frontend principale; il socket lo riattiva su richiesta. Porta 80 non legge
credenziali né inoltra richieste API: solo redirect GET/HEAD a URL costante;
POST è rifiutato. Host/Origin delle API sono vincolati all'origine HTTPS.

## Verifiche e limiti

- 100 test Linux passati sul target: hash, cambio obbligatorio, scadenza,
  logout, revoca, lockout persistente, CSRF, cookie e token bypass rifiutato.
- Browser Chromium su fixture HTTPS temporanea con dataplane fittizio:
  primo login, cambio, ricarica sessione, logout, tre errori e blocco; screenshot
  desktop/mobile in results/linux/ui-review/password. Non è un test radio.
- Target reale: redirect HTTP 308, HTTPS 200 con certificato verificato,
  login iniziale riuscito, accesso policy rifiutato prima del cambio e logout.
  Password iniziale lasciata all'utente; nessun cambio personale eseguito.
- Build ESP32 e test core/countdown passati; nessun flash.
- Listener osservati `192.168.7.1%phusb0:80` e `:443`.

Restano da validare elettricamente VBUS e fase bootloader. L'eccezione di banco
in /run scade al reboot: le unità web persistenti NON rendono automaticamente
sicuro o funzionante l'intero percorso USB dopo riavvio. Non riavviare con
cavo dati A–A inserito. Nessuna misura software può sostituire quella fisica.
