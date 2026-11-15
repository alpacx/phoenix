# Configurazione hotspot Linux

Rete → Hotspot Wi-Fi: attivazione, SSID (1–32 byte UTF-8), password WPA2
(8–63 caratteri ASCII). Password vuota mantiene quella salvata. Le API non
restituiscono mai la password. Il pannello avvisa della disconnessione dei
client Wi-Fi durante l'applicazione; l'interfaccia USB non viene modificata.

GET /api/v1/hotspot restituisce enabled (desiderato), active (confermato dai
processi e da hostapd), radio_state, clients, ssid, password_configured,
suspended, available. POST accetta enabled, ssid, password opzionale.
La capability hotspot_configuration nasconde i controlli sui backend privi
della funzione; il backend ESP32 non viene modificato.

Il worker serializza le modifiche e rifiuta l'applicazione durante comandi VPN,
speedtest o aggiornamenti. Riavvia esclusivamente hostapd/DHCP dell'AP, salva
atomicamente /var/lib/phoenix/hotspot-private.json (root-only 0600), ripristina
la configurazione precedente se l'applicazione/salvataggio fallisce. Al prossimo
avvio il file prevale sui valori iniziali di target.json. Un hotspot spento
intenzionalmente non fa scattare l'allarme di guasto AP né blocca la VPN USB.

Con la stessa radio usata come uplink Wi-Fi l'AP è sospeso; abilitarlo in quella
condizione è rifiutato. Con Ethernet uplink, USB e AP possono coesistere. Il
ritorno a Ethernet riattiva l'AP solo se desiderato enabled. Non cambia le
policy firewall o la modalità VPN/diretta.

Configurazione attuale: 2,4 GHz, canale 6, SSID non nascosto. Il control socket
hostapd risiede nella directory privata /run/phoenix/ap/control. Lo stato
ENABLED conferma il servizio, non la ricezione radio del telefono.

ROCK 4C+: iw phy conferma bande 2,4 e 5 GHz, ma la combinazione che comprende
AP ammette un solo AP e un solo canale. Nessuna promessa di due hotspot
simultanei sulle due bande. La selezione della banda non è ancora esposta.
