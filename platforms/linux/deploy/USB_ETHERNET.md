# USB Ethernet — implementazione offline, prova ROCK ancora necessaria

Phoenix può creare un gadget configfs con una sola funzione **CDC-ECM oppure
CDC-NCM**, quindi gestire DHCP sulla rete USB `192.168.7.0/24`. La rete usa le
stesse policy USB, NAT, port forwarding, blocco iniziale e WireGuard del backend
Linux. Il Wi-Fi STA può essere l'uplink in alternativa all'Ethernet; il servizio
USB non dipende dall'AP e resta distinto dal cambio AP/STA.

Non è stato verificato il riconoscimento da macOS, il kernel della ROCK, il
ruolo OTG, il cablaggio o il VBUS. Non è stata misurata velocità USB. Il descrittore
è conservativo USB 2.0; non costituisce una promessa di link SuperSpeed. La
versione/velocità effettiva va controllata sul banco prima di ottimizzarla.

## Separazione dei privilegi

`phoenix-usb-gadget.service` è un oneshot separato, opt-in. Crea solo
`/sys/kernel/config/usb_gadget/phoenix`, associa il controller **per ultimo** e
rimuove soltanto la propria configurazione. Non monta configfs, non carica
moduli, non scrive ruoli USB/regolatori e non adotta un gadget Radxa/ADB già
presente. Se la UDC è occupata o l'interfaccia esiste, l'avvio fallisce.
Il worker continua a non avere accesso in scrittura a configfs.

Il worker aggiunge indirizzo e DHCP solo dopo la barriera firewall. Rifiuta
interfacce gestite da NetworkManager, indirizzi IPv4 estranei e sovrapposizioni
con le route esistenti. Il servizio DHCP usa esclusivamente l'interfaccia USB;
non è un resolver DNS. Arresto/errore rimuovono l'indirizzo aggiunto da Phoenix.
La morte del DHCP o la rimozione del binding bloccano l'inoltro al successivo tick.
Un semplice scollegamento del cavo non richiede di ricreare il gadget.

## Preparazione sul target, quando disponibile

Non eseguire questa procedura sul Mac. Per la ROCK 4C+ resta aperta la verifica
fisica dei 5 V sulla USB-A OTG: **non collegare il cavo al Mac finché non è risolta**.
`vbus_verified` è una conferma dell'operatore dopo la verifica, non una misura
eseguita dal programma e non un comando per spegnere l'alimentazione.

1. Identificare modello, immagine/kernel, UDC e servizi USB presenti:
   `PYTHONPATH=/opt/phoenix/platforms/linux/service python3 -m phoenix_linux.usb_gadget inspect`.
   Un elenco UDC vuoto richiede prima la configurazione del kernel/ruolo periferica.
2. Verificare supporto configfs/libcomposite e della funzione scelta. Predisporre
   i moduli richiesti e il mount configfs con la procedura della distribuzione.
   L'osservazione storica del kernel Radxa b60 indicava ECM disponibile e NCM
   non selezionato: ricontrollare il kernel effettivamente installato.
3. Risolvere esplicitamente eventuali servizi gadget preesistenti, conservandone
   la configurazione. Phoenix non arresta né cancella automaticamente Radxa/ADB.
4. Assegnare una interfaccia USB dedicata, per esempio `phusb0`, anche in
   `interfaces.usb` di `/etc/phoenix/target.json`. Prima di crearla, renderla
   non gestita da NetworkManager con una configurazione persistente limitata
   **a quel nome**. Non disabilitare NetworkManager globalmente.
5. Aggiungere l'oggetto seguente con valori verificati sul target:

```json
"usb_gadget": {
  "enabled": true,
  "function": "ecm",
  "udc": "NOME_ESATTO_DA_SYS_CLASS_UDC",
  "serial": "IDENTIFICATIVO_UNIVOCO_STABILE",
  "vendor_id": "0xVVVV",
  "product_id": "0xPPPP",
  "vbus_verified": false,
  "dns": "103.86.96.100"
}
```

VID/PID sono segnaposto volutamente non validi: usare identificativi autorizzati
per il dispositivo/banco, non distribuire identificativi presi da altri prodotti.
Non è previsto fallback automatico NCM→ECM: scegliere la funzione supportata,
poi provarla con il Mac. I due MAC locali vengono derivati dal seriale, che deve
essere diverso per ogni dispositivo. Arrestare il gadget prima di modificare
funzione, identificativi o nome interfaccia.

6. L'installatore iniziale include l'unità nuova senza avviarla. Per una
   installazione esistente, installare sul target la copia revisionata di
   `platforms/linux/deploy/phoenix-usb-gadget.service` in `/etc/systemd/system/`.
   Aggiungere un drop-in di `phoenix-control.service`:

```ini
[Unit]
BindsTo=phoenix-usb-gadget.service
After=phoenix-usb-gadget.service
```

7. Solo dopo le verifiche elettriche, impostare `vbus_verified: true`, eseguire
   `systemctl daemon-reload`, arrestare il worker e riavviarlo: il drop-in fa
   partire il gadget prima del DHCP. Fermare il worker prima di rimuovere il
   drop-in o disabilitare USB. Nessuna di queste azioni è stata eseguita offline.

## Prova con il Mac

Dopo la connessione sicura del cavo, verificare che il Mac riceva un indirizzo
`192.168.7.20–200`, router `192.168.7.1`. Per il pannello resta il deployment
HTTPS via SSH, senza esporre automaticamente nuove porte web:

```sh
ssh -L 8443:127.0.0.1:8443 UTENTE_ROCK@192.168.7.1
```

Aprire `https://127.0.0.1:8443`, verificare il certificato come descritto nella
[guida deployment](README.md) e usare il proprio token amministrativo.
Selezionare l'uplink realmente collegato e connettere la VPN. All'avvio non si
naviga finché il traffico non è autorizzato: non c'è fallback diretto automatico.
Per provare davvero Phoenix, evitare che il Mac usi contemporaneamente un'altra
uscita Internet; nessuna preferenza o route del Mac viene modificata dal software.
Il cambio DNS aggiorna DHCP, ma un client con lease già acquisita può richiedere
rinnovo della lease o riconnessione USB prima di usare il nuovo DNS.

## Evidenze senza scheda

- Test con modello configfs: ECM/NCM, binding per ultimo, rollback, rifiuto di
  controller/configurazioni estranee e gate VBUS. **Non sono enumerazione USB.**
- Test unitari di ownership, DHCP, conflitti, cleanup e blocco su errore.
- `tests/integration/check_usb_dhcp.py`: scambio reale DHCP Discover/Offer/Request/
  ACK con dnsmasq su veth nel container; gateway/DNS, cambio DNS e cleanup.
- Test kernel esistente: regole nftables blocked/direct/vpn e route WireGuard
  dentro namespace isolato. Nessun account VPN reale o throughput misurato.

Riferimento implementativo: [Linux USB gadget configfs](https://docs.kernel.org/usb/gadget_configfs.html).
